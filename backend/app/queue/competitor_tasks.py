"""Celery tasks for competitor discovery and competitive analysis.

Houses the V2 competitive workflow:

* ``discover_competitors_task`` — runs CompetitorResearcherAgent and persists
  ProductCompetitor rows.
* ``functional_audit_task`` — generates a CompetitorFunctionalReport for one
  competitor (Stage 1 + Stage 2 LLM calls).
* ``mark_audits_complete`` — chord callback after all audits complete; marks the parent orchestration job successful.
* ``run_competitive_analysis_v2`` — orchestrates parallel audits via Celery chord.
"""

import traceback
from typing import Dict, Any
from celery import shared_task
from datetime import datetime, timezone

from app.database import SessionLocal
from app.models.competitor_intelligence import (
    CIProduct, ProductFeature, ProductCompetitor,
)
from app.models.competitive_reports import CompetitorAlert
from app.models.competitive_agent import CompetitiveAgentConfig
from app.services.queue_service import QueueService
from app.services.llm_service import LLMService
from app.services.competitive_report_metrics import count_gaps
from app.agents.competitor_researcher import CompetitorResearcherAgent
from app.utils.url import extract_domain
from app.utils.job_position import enrich_assessments
from app.queue.helpers import (
    get_db,
    _fetch_source_urls,
    _bump_parent_synthesis_progress,
    fail_job,
)

import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, name='app.queue.competitor_tasks.discover_competitors_task', soft_time_limit=600)
def discover_competitors_task(self, job_id: int) -> Dict[str, Any]:
    """
    Background task to discover competitors using CompetitorResearcherAgent.

    This task:
    1. Retrieves product analysis data
    2. Runs CompetitorResearcherAgent
    3. Stores discovered competitors in ProductCompetitor table
    4. Returns competitor IDs for feature extraction

    Args:
        job_id: QueueJob ID to process

    Returns:
        Dictionary with discovered competitor IDs
    """
    db = None
    try:
        db = get_db()
        queue_service = QueueService(db)

        # Mark job as running
        job = queue_service.mark_running(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        product_id = job.product_id
        user_id = job.user_id

        if not product_id:
            raise ValueError("Product ID is required")

        # Update progress
        queue_service.update_progress(job_id, 10.0, "Loading product data...")

        # Get product with analysis data
        product = db.query(CIProduct).filter(CIProduct.id == product_id).first()
        if not product:
            raise ValueError(f"Product {product_id} not found")

        if not product.structured_product_data:
            raise ValueError(f"Product {product_id} has not been analyzed yet")

        # Update progress
        queue_service.update_progress(job_id, 20.0, "Initializing competitor researcher...")

        # Create LLM service and agent
        llm_service = LLMService()
        agent = CompetitorResearcherAgent(
            db=db,
            llm_service=llm_service,
            product_id=product_id,
            user_id=user_id,
            job_id=job.job_uuid
        )

        # Load existing competitors for this product (for dedup + LLM context)
        existing_competitors = db.query(ProductCompetitor).filter(
            ProductCompetitor.product_id == product_id,
        ).all()

        # Build input from product analysis
        analysis = product.structured_product_data
        agent_input = {
            'product_name': product.product_name,
            'product_category': analysis.get('product_category', ''),
            'core_features': analysis.get('core_features', []),
            'target_users': analysis.get('target_users', ''),
            'competitor_search_keywords': analysis.get('competitor_search_keywords', []),
            'existing_competitors': [
                {'name': c.competitor_name, 'url': c.competitor_url or ''}
                for c in existing_competitors
                if c.status == 'active'
            ],
        }

        # Update progress
        queue_service.update_progress(job_id, 30.0, "Discovering competitors...")

        # Execute agent
        result = agent.execute(agent_input)

        # Update progress
        queue_service.update_progress(job_id, 70.0, "Storing competitors...")

        # Get agent config to check alert settings
        agent_config = db.query(CompetitiveAgentConfig).filter(
            CompetitiveAgentConfig.product_id == product_id
        ).first()
        alert_on_new = agent_config.alert_on_new_competitors if agent_config else False

        # Store discovered competitors
        competitors = result.get('competitors', [])
        competitor_ids = []
        competitor_names = []  # Track all competitor names for output_data
        new_competitor_names = []  # Track newly discovered competitors for alerts

        # Build lookup indexes from existing competitors (in Python, DB-agnostic)
        name_index = {c.competitor_name.lower(): c for c in existing_competitors}
        domain_index = {}
        for c in existing_competitors:
            domain = extract_domain(c.competitor_url or '')
            if domain:
                domain_index[domain] = c

        for comp_data in competitors:
            discovered_name = comp_data.get('name', '')
            discovered_url = comp_data.get('url', '')

            # Match by name (case-insensitive) first, then by URL domain
            existing = name_index.get(discovered_name.lower())
            if not existing:
                discovered_domain = extract_domain(discovered_url)
                if discovered_domain:
                    existing = domain_index.get(discovered_domain)

            if existing:
                # Update existing competitor
                existing.competitor_url = discovered_url or existing.competitor_url
                existing.status = 'active'
                competitor_ids.append(existing.id)
                competitor_names.append(existing.competitor_name)
            else:
                # Create new competitor
                new_competitor = ProductCompetitor(
                    product_id=product_id,
                    competitor_name=discovered_name,
                    competitor_url=discovered_url,
                    first_discovered_session_id=None,  # Queue-based, no session
                    status='active'
                )
                db.add(new_competitor)
                db.flush()
                competitor_ids.append(new_competitor.id)
                competitor_names.append(new_competitor.competitor_name)
                new_competitor_names.append({
                    'id': new_competitor.id,
                    'name': new_competitor.competitor_name
                })
                # Add to indexes so later items in this batch also dedup
                name_index[discovered_name.lower()] = new_competitor
                new_domain = extract_domain(discovered_url)
                if new_domain:
                    domain_index[new_domain] = new_competitor

        # Create alerts for newly discovered competitors
        created_alerts = []
        if alert_on_new and new_competitor_names:
            for comp in new_competitor_names:
                alert = CompetitorAlert(
                    product_id=product_id,
                    alert_type='new_competitor',
                    competitor_id=comp['id'],
                    competitor_name=comp['name'],
                    message=f"New competitor discovered: {comp['name']}",
                    is_read=False
                )
                db.add(alert)
                created_alerts.append(alert)

        db.commit()

        # Email a digest to product members (EDIT+). Never let a notification
        # failure fail the discovery job — alerts are already persisted above.
        if created_alerts:
            try:
                from app.services.alert_notification_service import AlertNotificationService
                AlertNotificationService(db).notify_new_competitors(
                    product_id=product_id,
                    alerts=[a.to_dict() for a in created_alerts],
                )
            except Exception:
                logger.exception(
                    "Failed to send competitor alert emails for product %s",
                    product_id,
                )

        # Update progress
        queue_service.update_progress(job_id, 90.0, "Finalizing...")

        # Prepare output data
        output_data = {
            'product_id': product_id,
            'competitors_discovered': len(competitors),
            'competitor_ids': competitor_ids,
            'competitor_names': competitor_names,
            'research_summary': result.get('research_summary', ''),
            'next_step': 'Run ci_run_competitor_audit for each competitor name, then ci_run_analysis for landscape synthesis.',
        }

        # Mark job as success
        queue_service.mark_success(job_id, output_data)

        return output_data

    except Exception as e:
        error_msg = str(e)
        error_tb = traceback.format_exc()
        print(f"[discover_competitors_task] Error: {error_msg}")
        print(f"[discover_competitors_task] Traceback: {error_tb}")

        fail_job(db, job_id, error_msg, error_tb, task_name="discover_competitors_task")

        raise

    finally:
        if db:
            db.close()


# DEPRECATED: extract_features_task, extract_features_parallel, and aggregate_extraction_results
# have been removed. Feature extraction is now handled by the V2 functional audit workflow.
# Use functional_audit_task to extract competitor features into CompetitorFunctionalReport.


# =============================================================================
# V2 Competitive Analysis Tasks (Functional Audit + Landscape Synthesis)
# =============================================================================

@shared_task(bind=True, name='app.queue.competitor_tasks.functional_audit_task', max_retries=2, default_retry_delay=60, soft_time_limit=900)
def functional_audit_task(self, job_id: int):
    """
    Run a functional audit for a single competitor.

    This task:
    1. Fetches competitor data and web search results
    2. Runs the CompetitorFunctionalAuditAgent
    3. Stores the report in the database
    4. Returns the report ID for aggregation

    Args:
        job_id: The QueueJob ID for this audit
    """
    from app.agents.functional_audit_agent import (
        CompetitorFunctionalAuditAgent,
        generate_markdown_report
    )
    from app.models.competitive_reports import (
        CompetitorFunctionalReport, ProductSelfAssessment,
    )
    from app.schemas.competitive_reports import (
        FunctionalAuditOutput, StoredFunctionalAuditOutput,
    )
    from app.services.llm_service import LLMService

    db = None
    job = None
    try:
        db = SessionLocal()
        queue_service = QueueService(db)

        # Get job details
        job = queue_service.get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        queue_service.mark_running(job_id)
        queue_service.update_progress(job_id, 5.0, "Loading competitor data...")

        # Extract job parameters
        input_data = job.input_data or {}
        competitor_id = input_data.get('competitor_id')
        product_id = job.product_id
        web_research_enabled = input_data.get('web_research_enabled', True)
        source_urls = input_data.get('source_urls') or []

        if not competitor_id:
            raise ValueError("competitor_id is required in input_data")

        # Get competitor info
        competitor = db.query(ProductCompetitor).filter(
            ProductCompetitor.id == competitor_id,
            ProductCompetitor.product_id == product_id
        ).first()

        if not competitor:
            raise ValueError(f"Competitor {competitor_id} not found for product {product_id}")

        # Get product context
        product = db.query(CIProduct).filter(CIProduct.id == product_id).first()
        queue_service.update_progress(job_id, 15.0, "Loading product context and job map...")
        product_context = {
            'product_name': product.product_name if product else 'Unknown',
            'product_category': product.product_category if product else None,
            'description': product.product_description if product else None,
        }

        # Load job map for JTBD analysis
        job_map = product.job_map if product else None
        target_customer_profile = product.target_customer_profile if product else None

        # Get product features for context
        features = db.query(ProductFeature).filter(
            ProductFeature.product_id == product_id,
            ProductFeature.status == 'active'
        ).limit(15).all()
        product_context['core_features'] = [f.feature_name for f in features]

        # Resolve web search results via per-competitor cache (Phase B).
        #
        # Priority order:
        #   1. Explicit web_search_results in input_data (legacy / tests)
        #   2. Fresh cache on ProductCompetitor (within TTL)
        #   3. Live refresh via CompetitorResearchCache (if web_research enabled)
        #   4. Empty (if caller disabled web_research and no cache exists)
        #
        # When we have cached/pre-fetched results, we flip effective_web_research
        # to False so the agent renders them into the prompt instead of running
        # the tool-use loop (which would duplicate work and cost more tokens).
        web_search_results = input_data.get('web_search_results') or []
        effective_web_research = web_research_enabled

        if not web_search_results:
            from app.services.competitor_research_cache import CompetitorResearchCache

            cache = CompetitorResearchCache(db)
            cached = cache.get_fresh(competitor)
            if cached is not None:
                web_search_results = cached
                effective_web_research = False
                queue_service.update_progress(
                    job_id, 25.0,
                    f"using cached research for {competitor.competitor_name}...",
                )
            elif web_research_enabled:
                queue_service.update_progress(
                    job_id, 20.0,
                    f"pre-fetching research for {competitor.competitor_name}...",
                )

                def _cache_progress(i: int, total: int) -> None:
                    pct = 20.0 + (i / total) * 5.0
                    queue_service.update_progress(
                        job_id, pct, f"fetching research {i}/{total}...",
                    )

                web_search_results = cache.refresh(
                    competitor, product_context, progress_cb=_cache_progress,
                )
                effective_web_research = False

        # Fetch any caller-supplied source URLs
        fetched_sources = _fetch_source_urls(
            source_urls,
            queue_service=queue_service,
            job_id=job_id,
            progress_start=25.0,
            progress_span=5.0,
        )

        # Query user-provided evidence for this competitor
        from app.models.evidence import Evidence
        competitor_evidence = db.query(Evidence).filter(
            Evidence.competitor_id == competitor_id,
            Evidence.product_id == product_id,
        ).order_by(Evidence.created_at.desc()).limit(20).all()

        user_provided_evidence = []
        for ev in competitor_evidence:
            user_provided_evidence.append({
                'title': ev.title,
                'content': ev.content[:2000] if ev.content else '',
                'evidence_type': ev.evidence_type.value if ev.evidence_type else None,
                'source_url': ev.source_url,
                'source_description': ev.source_description,
            })

        # Initialize LLM service and agent (Phase C: staged execution)
        #
        # effective_web_research may differ from the request param: when we've
        # already fetched cached or fresh results above, we pass them in the
        # prompt and don't need the agent's tool loop.
        #
        # Staged audit: Stage 1 produces competitor_context + functional_comparison
        # + technical_constraints (~45s). Stage 2 uses that output as conditioning
        # context and produces job_assessments + evidence_citations + gaps_deep_dive
        # (~90-150s). This gives the caller visible progress at ~50% instead of a
        # single ~4-minute wait.
        llm_service = LLMService()
        agent = CompetitorFunctionalAuditAgent(
            db=db,
            llm_service=llm_service,
            product_id=product_id,
            user_id=job.user_id,
            job_id=job.job_uuid,
            web_research_enabled=effective_web_research,
        )

        agent_input = {
            'competitor_name': competitor.competitor_name,
            'competitor_url': competitor.competitor_url or '',
            'product_context': product_context,
            'web_search_results': web_search_results,
            'user_provided_evidence': user_provided_evidence,
            'fetched_sources': fetched_sources,
        }
        if job_map:
            agent_input["job_map"] = job_map
        if target_customer_profile:
            agent_input["target_customer_profile"] = target_customer_profile

        # --- Stage 1: context + comparison + technical_constraints ---
        queue_service.update_progress(
            job_id, 30.0,
            f"generating competitor context for {competitor.competitor_name}...",
        )
        stage_1 = agent.execute_stage_1(agent_input, max_tokens=8000)

        # --- Stage 2: job_assessments + evidence_citations + gaps_deep_dive ---
        queue_service.update_progress(
            job_id, 50.0,
            "context ready, generating job assessments...",
        )
        stage_2_input = {**agent_input, "stage_1_output": stage_1}
        stage_2 = agent.execute_stage_2(stage_2_input, max_tokens=12000)

        queue_service.update_progress(job_id, 75.0, "finalizing job assessments...")

        # Merge the two stage outputs into the full schema shape that downstream
        # consumers (report generator, report row, synthesis) expect. Stage-specific
        # keys are additive, so `**stage_1, **stage_2` is sufficient.
        result = {**stage_1, **stage_2}
        # Validate the merged payload against the full schema before persisting —
        # gives us a single clean failure point if either stage dropped a required field.
        result = FunctionalAuditOutput(**result).model_dump()

        # Store or update the report
        existing_report = db.query(CompetitorFunctionalReport).filter(
            CompetitorFunctionalReport.product_competitor_id == competitor_id,
            CompetitorFunctionalReport.product_id == product_id
        ).first()

        # Capture previous data for change detection before overwriting.
        # job_assessments carries the stable (job, position) coordinate the diff
        # compares, and the human review state that must survive a re-audit.
        previous_data = None
        previous_assessments = None
        if existing_report:
            previous_assessments = existing_report.job_assessments or []
            previous_data = {
                "functional_comparison": existing_report.functional_comparison or [],
                "competitor_context": existing_report.competitor_context or {},
                "gaps_deep_dive": existing_report.gaps_deep_dive or [],
                "job_assessments": previous_assessments,
            }

        # Our score comes from the product's own self-assessment, not from this audit.
        # Without one, the audit still reports what the competitor does — position just
        # cannot be stated, because it needs both sides.
        self_assessment = db.query(ProductSelfAssessment).filter(
            ProductSelfAssessment.product_id == product_id
        ).order_by(ProductSelfAssessment.assessment_version.desc()).first()
        self_entries = [
            entry for entry in ((self_assessment.job_assessments or []) if self_assessment else [])
            if isinstance(entry, dict) and entry.get("job_id")
        ]
        self_scores = {e["job_id"]: e.get("score") for e in self_entries}
        # Confidence travels with the score: a verdict is only as good as our side of it,
        # and one built on an ungrounded self-score must not render as authoritative.
        self_confidences = {e["job_id"]: e.get("confidence") for e in self_entries}

        # Join our score in, derive system_position, and carry forward any PM overrides
        # from the previous version — a re-audit regenerates the system verdict alongside
        # a human's, never on top of it.
        enriched_assessments = enrich_assessments(
            result.get("job_assessments"),
            previous_assessments,
            self_scores=self_scores,
            self_assessment_version=(
                self_assessment.assessment_version if self_assessment else None
            ),
            self_confidences=self_confidences,
        )

        queue_service.update_progress(job_id, 85.0, "Generating report...")

        # Build the report from the enriched assessments rather than the agent's raw
        # output, so the export shows our score wherever a self-assessment exists.
        result_model = StoredFunctionalAuditOutput(
            **{**result, "job_assessments": enriched_assessments}
        )
        markdown_content = generate_markdown_report(competitor.competitor_name, result_model)

        if existing_report:
            # Update existing report
            existing_report.report_version += 1
            existing_report.report_content_md = markdown_content
            existing_report.competitor_context = result['competitor_context']
            existing_report.functional_comparison = result['functional_comparison']
            existing_report.gaps_deep_dive = result['gaps_deep_dive']
            existing_report.technical_constraints = result['technical_constraints']
            existing_report.raw_search_results = web_search_results if isinstance(web_search_results, list) else None
            existing_report.queue_job_id = job_id
            # Store JTBD fields (may be empty if no job map)
            existing_report.job_assessments = enriched_assessments
            existing_report.evidence_citations = result.get("evidence_citations")
            existing_report.unmapped_capabilities = result.get("unmapped_capabilities")
            report = existing_report
        else:
            # Create new report
            report = CompetitorFunctionalReport(
                product_competitor_id=competitor_id,
                product_id=product_id,
                report_version=1,
                report_content_md=markdown_content,
                competitor_context=result['competitor_context'],
                functional_comparison=result['functional_comparison'],
                gaps_deep_dive=result['gaps_deep_dive'],
                technical_constraints=result['technical_constraints'],
                raw_search_results=web_search_results if isinstance(web_search_results, list) else None,
                queue_job_id=job_id,
                # JTBD fields (may be empty if no job map)
                job_assessments=enriched_assessments,
                evidence_citations=result.get("evidence_citations"),
                unmapped_capabilities=result.get("unmapped_capabilities"),
            )
            db.add(report)

        db.commit()
        db.refresh(report)

        # Mark the competitor as successfully audited (drives synthesis eligibility
        # and the "has been audited" summary in MCP tools)
        now = datetime.now(timezone.utc)
        competitor.audit_status = "completed"
        competitor.audit_last_run = now

        # Update the product-level CompetitiveAgentConfig so the UI "last run"
        # indicator reflects manual audits, not just scheduler runs.
        agent_config = db.query(CompetitiveAgentConfig).filter(
            CompetitiveAgentConfig.product_id == product_id
        ).first()
        if agent_config:
            agent_config.deep_analysis_last_run = now

        db.commit()

        # Compute structured diff from previous version
        if previous_data:
            try:
                from app.services.change_detection_service import ChangeDetectionService
                current_data = {
                    "functional_comparison": result['functional_comparison'],
                    "competitor_context": result['competitor_context'],
                    "gaps_deep_dive": result['gaps_deep_dive'],
                    "job_assessments": enriched_assessments,
                }
                report.changes_from_previous = ChangeDetectionService.compute_functional_report_diff(
                    current_data, previous_data
                )
                db.commit()
            except Exception as diff_err:
                print(f"[functional_audit_task] Warning: Change detection failed: {diff_err}")

        # Increment citation counts for evidence referenced in this report
        try:
            from app.services.evidence_service import increment_evidence_citations

            cited_ids: set = set()

            # evidence_citations: list of {evidence_id, finding_type, ...}
            for citation in (result.get("evidence_citations") or []):
                if isinstance(citation, dict) and citation.get("evidence_id") is not None:
                    cited_ids.add(citation["evidence_id"])

            # job_assessments[*].features[*].evidence_ids
            for assessment in (result.get("job_assessments") or []):
                if not isinstance(assessment, dict):
                    continue
                for feature in (assessment.get("features") or []):
                    if not isinstance(feature, dict):
                        continue
                    for eid in (feature.get("evidence_ids") or []):
                        if eid is not None:
                            cited_ids.add(eid)

            if cited_ids:
                increment_evidence_citations(
                    db,
                    list(cited_ids),
                    f"functional_report:{report.id}",
                )
                db.commit()
        except Exception as cite_err:
            print(f"[functional_audit_task] Warning: Citation increment failed: {cite_err}")

        # output_data envelope is partial-write-ready: `stages_completed` +
        # `stage_1_output` + `stage_2_output` let a future follow-up write
        # Stage 1 at the 50% mark so pollers can read it mid-flight. The
        # top-level keys (report_id, features_compared, gaps_identified) are
        # preserved for existing consumers.
        output_data = {
            'report_id': report.id,
            'competitor_id': competitor_id,
            'competitor_name': competitor.competitor_name,
            'report_version': report.report_version,
            'features_compared': len(result['functional_comparison']),
            # Use the unified helper that prefers functional_comparison, falls
            # back to job_assessments. Pre-PR-#33 the gap count came from
            # gaps_deep_dive but the JTBD redesign moved gaps into the per-job
            # features array; reading the legacy field always returned 0 once
            # job maps existed.
            'gaps_identified': count_gaps(result),
            'stages_completed': ['stage_1', 'stage_2'],
            'stage_1_output': stage_1,
            'stage_2_output': stage_2,
        }

        queue_service.mark_success(job_id, output_data)

        # If this audit was triggered by a unified_synthesis_task, bump that
        # parent's progress so the user sees mid-flight progress on the
        # synthesis page during the long audit window.
        if job.parent_job_id:
            _bump_parent_synthesis_progress(db, job.parent_job_id)

        return output_data

    except Exception as e:
        error_msg = str(e)
        error_tb = traceback.format_exc()
        print(f"[functional_audit_task] Error for job {job_id}: {error_msg}")

        fail_job(db, job_id, error_msg, error_tb, task_name="functional_audit_task")
        # Even on failure, bump the parent so users see the failed
        # audit count toward the "N of M complete" total.
        try:
            if db and job and job.parent_job_id:
                _bump_parent_synthesis_progress(db, job.parent_job_id)
        except Exception:
            pass

        raise self.retry(exc=e)

    finally:
        if db:
            db.close()


@shared_task(bind=True, name='app.queue.competitor_tasks.mark_audits_complete', soft_time_limit=300)
def mark_audits_complete(self, audit_results: list, parent_job_id: int):
    """
    Chord callback after all functional_audit_task instances complete.

    Marks the parent orchestration job (SCHEDULED_DEEP_ANALYSIS) successful
    with a summary of audit outcomes. Synthesis is decoupled — the user
    triggers unified_synthesis separately after reviewing audit results.

    Args:
        audit_results: List of return values from functional_audit_task
        parent_job_id: The parent orchestration job ID
    """
    db = None
    try:
        db = SessionLocal()
        queue_service = QueueService(db)

        successful_audits = [r for r in audit_results if r and r.get('report_id')]
        failed_audits = len(audit_results) - len(successful_audits)

        print(f"[mark_audits_complete] {len(successful_audits)} successful, {failed_audits} failed")

        queue_service.mark_success(parent_job_id, {
            'status': 'audits_completed',
            'successful_audits': len(successful_audits),
            'failed_audits': failed_audits,
            'audit_report_ids': [r['report_id'] for r in successful_audits],
        })

        return {
            'status': 'audits_completed',
            'successful_audits': len(successful_audits),
            'failed_audits': failed_audits,
        }

    except Exception as e:
        error_msg = str(e)
        error_tb = traceback.format_exc()
        print(f"[mark_audits_complete] Error: {error_msg}")

        fail_job(db, parent_job_id, error_msg, error_tb, task_name="mark_audits_complete")

        raise

    finally:
        if db:
            db.close()


@shared_task(bind=True, name='app.queue.competitor_tasks.run_competitive_analysis_v2', soft_time_limit=900)
def run_competitive_analysis_v2(self, job_id: int):
    """
    Orchestrate the V2 competitive analysis workflow.

    This task:
    1. Creates functional audit jobs for all enabled competitors
    2. Dispatches audits in parallel using Celery chord
    3. Chord callback marks the parent job complete

    Args:
        job_id: The parent orchestration job ID
    """
    from celery import chord
    from app.models.queue import QueueJob, JobType, JobStatus

    db = None
    try:
        db = SessionLocal()
        queue_service = QueueService(db)

        # Get job details
        job = queue_service.get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        queue_service.mark_running(job_id)

        product_id = job.product_id

        # Get tracked competitors
        competitors = db.query(ProductCompetitor).filter(
            ProductCompetitor.product_id == product_id,
            ProductCompetitor.status == 'active',
            ProductCompetitor.tracked == True
        ).all()

        if not competitors:
            raise ValueError(f"No tracked competitors. Track competitors in the competitor list first.")

        print(f"[run_competitive_analysis_v2] Starting analysis for {len(competitors)} competitors")

        # Create audit jobs for each competitor
        audit_tasks = []
        audit_job_ids = []

        for competitor in competitors:
            # Create job record
            audit_job = QueueJob(
                job_type=JobType.FUNCTIONAL_AUDIT,
                status=JobStatus.PENDING,
                product_id=product_id,
                parent_job_id=job_id,
                input_data={
                    'competitor_id': competitor.id,
                    'competitor_name': competitor.competitor_name,
                }
            )
            db.add(audit_job)
            db.flush()  # Get ID without committing

            audit_job_ids.append(audit_job.id)
            audit_tasks.append(functional_audit_task.s(audit_job.id))

        db.commit()

        # Update parent job with child job IDs
        job.output_data = {
            'status': 'audits_dispatched',
            'audit_job_ids': audit_job_ids,
            'competitor_count': len(competitors),
        }
        db.commit()

        # Dispatch parallel audits; callback marks the parent job complete
        workflow = chord(audit_tasks)(mark_audits_complete.s(job_id))

        return {
            'status': 'workflow_started',
            'audit_jobs': len(audit_job_ids),
            'competitors': [c.competitor_name for c in competitors],
        }

    except Exception as e:
        error_msg = str(e)
        error_tb = traceback.format_exc()
        print(f"[run_competitive_analysis_v2] Error for job {job_id}: {error_msg}")

        fail_job(db, job_id, error_msg, error_tb, task_name="run_competitive_analysis_v2")

        raise

    finally:
        if db:
            db.close()
