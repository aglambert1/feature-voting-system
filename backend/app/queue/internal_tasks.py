"""Celery tasks for processing internal CRM/support imports.

* ``internal_discovery_task`` — runs InternalDiscoveryAgent across deals +
  support tickets to extract WinLossTheme and SupportTheme records, links each
  to its best-matching ProductJob, and bridges every theme to the evidence
  factbase.
* ``activity_insight_task`` — per-deal/aggregate activity analysis that
  produces DealActivityInsight + SupportActivityInsight records on an
  ActivityImport.
"""

import traceback
from typing import Dict, Optional
from celery import shared_task

from app.database import SessionLocal
from app.services.queue_service import QueueService
from app.queue.helpers import _cosine_similarity, _maybe_suggest_need


# =============================================================================
# Internal Discovery Task (Three-Source Synthesis)
# =============================================================================

@shared_task(bind=True, name='app.queue.internal_tasks.internal_discovery_task', max_retries=2, default_retry_delay=60, soft_time_limit=600)
def internal_discovery_task(self, job_id: int):
    """
    Process uploaded internal feedback data to extract themes.

    This task:
    1. Retrieves the imported data from the database
    2. Runs the InternalDiscoveryAgent to extract themes
    3. Stores WinLossTheme and SupportTheme records
    4. Updates the import status

    Args:
        job_id: The QueueJob ID for this task
    """
    from app.agents.internal_discovery_agent import InternalDiscoveryAgent
    from app.models.internal_feedback import (
        InternalFeedbackImport,
        WinLossTheme,
        SupportTheme
    )
    from app.schemas.internal_feedback import InternalDiscoveryOutput
    from app.services.llm_service import LLMService
    from datetime import datetime, timezone

    db = None
    try:
        db = SessionLocal()
        queue_service = QueueService(db)

        # Get job details
        job = queue_service.get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        queue_service.mark_running(job_id)
        user_id = job.user_id

        # Extract job parameters
        input_data = job.input_data or {}
        import_id = input_data.get('import_id')
        deals = input_data.get('deals', [])
        support_tickets = input_data.get('support_tickets', [])

        if not import_id:
            raise ValueError("import_id is required in input_data")

        # Get import record
        import_record = db.query(InternalFeedbackImport).filter(
            InternalFeedbackImport.id == import_id
        ).first()

        if not import_record:
            raise ValueError(f"Import {import_id} not found")

        # Initialize LLM service and agent
        llm_service = LLMService()
        agent = InternalDiscoveryAgent(
            db=db,
            llm_service=llm_service,
            product_id=import_record.product_id,
            user_id=user_id,
            job_id=job.job_uuid
        )

        # Run the agent
        result = agent.execute({
            'deals': deals,
            'support_tickets': support_tickets
        })

        # Parse output
        if isinstance(result, InternalDiscoveryOutput):
            output = result
        else:
            output = InternalDiscoveryOutput(**result)

        # Pre-load active ProductJobs and pre-embed JTBD statements so we can
        # link each new theme to its best-matching job in one batch.
        from app.models.competitor_intelligence import ProductJob
        product_jobs = db.query(ProductJob).filter(
            ProductJob.product_id == import_record.product_id,
            ProductJob.status == "active",
        ).all()
        active_jobs_with_emb = [j for j in product_jobs if j.statement_embedding]

        winloss_jtbds = [t.jtbd_statement for t in output.winloss_themes if t.jtbd_statement]
        support_jtbds = [t.jtbd_statement for t in output.support_themes if t.jtbd_statement]
        winloss_embs: Dict[str, list] = {}
        support_embs: Dict[str, list] = {}
        if active_jobs_with_emb and (winloss_jtbds or support_jtbds):
            try:
                from app.services.embedding_service import generate_embeddings_batch
                if winloss_jtbds:
                    embs = generate_embeddings_batch(winloss_jtbds, input_type="document")
                    winloss_embs = dict(zip(winloss_jtbds, embs))
                if support_jtbds:
                    embs = generate_embeddings_batch(support_jtbds, input_type="document")
                    support_embs = dict(zip(support_jtbds, embs))
            except Exception as emb_err:
                print(f"[internal_discovery_task] Warning: JTBD embedding for themes failed: {emb_err}")

        def _match_job_for_jtbd(emb: Optional[list], threshold: float = 0.5) -> Optional[str]:
            if not emb:
                return None
            best_key = None
            best_sim = 0.0
            for j in active_jobs_with_emb:
                sim = _cosine_similarity(emb, j.statement_embedding)
                if sim > best_sim and sim > threshold:
                    best_sim = sim
                    best_key = j.job_id_key
            return best_key

        # Store win/loss themes
        winloss_db_themes = []
        winloss_db_embs = []
        for theme in output.winloss_themes:
            jtbd_emb = winloss_embs.get(theme.jtbd_statement) if theme.jtbd_statement else None
            matched_job_key = _match_job_for_jtbd(jtbd_emb)
            db_theme = WinLossTheme(
                import_id=import_id,
                product_id=import_record.product_id,
                theme_name=theme.theme_name,
                outcome=theme.outcome,
                competitor_name=theme.competitor_correlation,
                deal_count=theme.deal_count,
                total_value=theme.total_value,
                sample_reasons=theme.sample_reasons,
                feature_keywords=theme.feature_keywords,
                jtbd_statement=theme.jtbd_statement,
                job_id_key=matched_job_key,
            )
            db.add(db_theme)
            winloss_db_themes.append(db_theme)
            winloss_db_embs.append(jtbd_emb)

        # Store support themes
        support_db_themes = []
        support_db_embs = []
        for theme in output.support_themes:
            jtbd_emb = support_embs.get(theme.jtbd_statement) if theme.jtbd_statement else None
            matched_job_key = _match_job_for_jtbd(jtbd_emb)
            db_theme = SupportTheme(
                import_id=import_id,
                product_id=import_record.product_id,
                theme_name=theme.theme_name,
                category=theme.category,
                ticket_count=theme.ticket_count,
                sample_subjects=theme.sample_subjects,
                feature_keywords=theme.feature_keywords,
                urgency_indicator=theme.urgency_indicator,
                jtbd_statement=theme.jtbd_statement,
                job_id_key=matched_job_key,
            )
            db.add(db_theme)
            support_db_themes.append(db_theme)
            support_db_embs.append(jtbd_emb)

        db.flush()  # Get IDs before creating suggestions

        # Surface unmatched/weak-match themes as need map suggestions
        for db_theme, jtbd_emb in zip(winloss_db_themes, winloss_db_embs):
            _maybe_suggest_need(
                db,
                product_id=import_record.product_id,
                signal_type="win_loss_theme",
                signal_id=db_theme.id,
                signal_content=db_theme.theme_name,
                jtbd_embedding=jtbd_emb,
            )
        for db_theme, jtbd_emb in zip(support_db_themes, support_db_embs):
            _maybe_suggest_need(
                db,
                product_id=import_record.product_id,
                signal_type="support_theme",
                signal_id=db_theme.id,
                signal_content=db_theme.theme_name,
                jtbd_embedding=jtbd_emb,
            )

        # Bridge themes to evidence factbase
        from app.models.evidence import EvidenceType
        from app.services.evidence_service import create_evidence, resolve_competitor_by_name

        evidence_count = 0
        for theme in output.winloss_themes:
            # Build content from theme details
            content_parts = [f"Win/Loss Theme: {theme.theme_name}"]
            content_parts.append(f"Outcome: {theme.outcome}")
            content_parts.append(f"Deal count: {theme.deal_count}, Total value: ${theme.total_value:,.0f}")
            if theme.sample_reasons:
                content_parts.append("Sample reasons: " + "; ".join(theme.sample_reasons[:3]))
            if theme.jtbd_statement:
                content_parts.append(f"JTBD: {theme.jtbd_statement}")

            # Resolve competitor if correlated
            competitor_id = None
            if theme.competitor_correlation:
                matched = resolve_competitor_by_name(db, import_record.product_id, theme.competitor_correlation)
                if matched:
                    competitor_id = matched.id

            try:
                create_evidence(
                    db=db,
                    product_id=import_record.product_id,
                    evidence_type=EvidenceType.CUSTOMER_INTERVIEW,
                    title=f"Win/Loss: {theme.theme_name}",
                    content="\n".join(content_parts),
                    source_description=f"CRM import #{import_id}",
                    competitor_id=competitor_id,
                    tags=theme.feature_keywords[:5] if theme.feature_keywords else None,
                    created_by="crm_import",
                )
                evidence_count += 1
            except Exception as e:
                print(f"[internal_discovery_task] Evidence creation failed for winloss theme: {e}")

        for theme in output.support_themes:
            content_parts = [f"Support Theme: {theme.theme_name}"]
            content_parts.append(f"Category: {theme.category}, Urgency: {theme.urgency_indicator}")
            content_parts.append(f"Ticket count: {theme.ticket_count}")
            if theme.sample_subjects:
                content_parts.append("Sample subjects: " + "; ".join(theme.sample_subjects[:3]))
            if theme.jtbd_statement:
                content_parts.append(f"JTBD: {theme.jtbd_statement}")

            try:
                create_evidence(
                    db=db,
                    product_id=import_record.product_id,
                    evidence_type=EvidenceType.CUSTOMER_INTERVIEW,
                    title=f"Support: {theme.theme_name}",
                    content="\n".join(content_parts),
                    source_description=f"CRM import #{import_id}",
                    tags=theme.feature_keywords[:5] if theme.feature_keywords else None,
                    created_by="crm_import",
                )
                evidence_count += 1
            except Exception as e:
                print(f"[internal_discovery_task] Evidence creation failed for support theme: {e}")

        # Update import record
        import_record.status = "completed"
        import_record.themes_extracted = True
        import_record.analysis_summary = output.analysis_summary
        import_record.processed_at = datetime.now(timezone.utc)

        db.commit()

        # Mark job success
        queue_service.mark_success(job_id, {
            'import_id': import_id,
            'winloss_themes_count': len(output.winloss_themes),
            'support_themes_count': len(output.support_themes),
            'evidence_created': evidence_count,
            'deals_analyzed': output.deals_analyzed,
            'tickets_analyzed': output.tickets_analyzed
        })

        return {
            'status': 'completed',
            'import_id': import_id,
            'winloss_themes': len(output.winloss_themes),
            'support_themes': len(output.support_themes)
        }

    except Exception as e:
        error_msg = str(e)
        error_tb = traceback.format_exc()
        print(f"[internal_discovery_task] Error for job {job_id}: {error_msg}")

        if db:
            try:
                queue_service = QueueService(db)
                queue_service.mark_failure(job_id, error_msg, error_tb)

                # Update import record status
                input_data = queue_service.get_job(job_id).input_data or {}
                import_id = input_data.get('import_id')
                if import_id:
                    import_record = db.query(InternalFeedbackImport).filter(
                        InternalFeedbackImport.id == import_id
                    ).first()
                    if import_record:
                        import_record.status = "failed"
                        import_record.error_message = error_msg
                        db.commit()
            except Exception:
                pass

        raise

    finally:
        if db:
            db.close()


@shared_task(bind=True, name='app.queue.internal_tasks.activity_insight_task', soft_time_limit=600)
def activity_insight_task(self, job_id: int):
    """
    Process CRM activity data to extract product insights.

    This task:
    1. Retrieves the parsed activity data from the import record
    2. Runs the ActivityInsightAgent for per-deal and aggregate analysis
    3. Stores DealActivityInsight and SupportActivityInsight records
    4. Updates the import status with analysis summary

    Args:
        job_id: The QueueJob ID for this task
    """
    from app.agents.activity_insight_agent import ActivityInsightAgent
    from app.models.activity_insights import (
        ActivityImport,
        DealActivityInsight,
        SupportActivityInsight
    )
    from app.services.llm_service import LLMService
    from datetime import datetime, timezone

    db = None
    try:
        db = SessionLocal()
        queue_service = QueueService(db)

        # Get job details
        job = queue_service.get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        queue_service.mark_running(job_id)
        user_id = job.user_id
        queue_service.update_progress(job_id, 10.0, "Loading activity data...")

        # Extract job parameters
        input_data = job.input_data or {}
        import_id = input_data.get('import_id')
        parsed_data = input_data.get('parsed_data', {})

        if not import_id:
            raise ValueError("import_id is required in input_data")

        # Get import record
        import_record = db.query(ActivityImport).filter(
            ActivityImport.id == import_id
        ).first()

        if not import_record:
            raise ValueError(f"Activity import {import_id} not found")

        queue_service.update_progress(job_id, 20.0, "Initializing activity insight agent...")

        # Initialize LLM service and agent
        llm_service = LLMService()
        agent = ActivityInsightAgent(
            db=db,
            llm_service=llm_service,
            product_id=import_record.product_id,
            user_id=user_id,
            job_id=job.job_uuid
        )

        queue_service.update_progress(job_id, 30.0, "Analyzing deal activities...")

        # Run the agent with higher max_tokens for detailed activity analysis
        # The output includes multiple deal insights, each with quotes, keywords, etc.
        result = agent.execute(parsed_data, max_tokens=8000)

        queue_service.update_progress(job_id, 70.0, "Storing insights...")

        # Store deal activity insights
        for insight in result.get('deal_insights', []):
            db_insight = DealActivityInsight(
                import_id=import_id,
                product_id=import_record.product_id,
                deal_id=insight.get('deal_id'),
                deal_name=insight.get('deal_name'),
                deal_outcome=insight.get('deal_outcome', 'unknown'),
                deal_value=insight.get('deal_value'),
                competitor_mentioned=insight.get('competitor_mentioned'),
                theme_name=insight.get('theme_name'),
                category=insight.get('category', 'feature_gap'),
                sentiment=insight.get('sentiment', 'neutral'),
                urgency_level=insight.get('urgency_level', 'medium'),
                sample_quotes=insight.get('sample_quotes', []),
                activity_count=insight.get('activity_count', 1),
                feature_keywords=insight.get('feature_keywords', [])
            )
            db.add(db_insight)

        # Store support activity insights
        for insight in result.get('support_insights', []):
            db_insight = SupportActivityInsight(
                import_id=import_id,
                product_id=import_record.product_id,
                theme_name=insight.get('theme_name'),
                category=insight.get('category', 'feature_gap'),
                ticket_count=insight.get('ticket_count', 0),
                urgency_level=insight.get('urgency_level', 'medium'),
                sample_quotes=insight.get('sample_quotes', []),
                accounts_affected=insight.get('accounts_affected', []),
                feature_keywords=insight.get('feature_keywords', [])
            )
            db.add(db_insight)

        queue_service.update_progress(job_id, 90.0, "Finalizing...")

        # Update import record
        import_record.status = "completed"
        import_record.analysis_summary = result.get('analysis_summary')
        import_record.top_loss_themes = result.get('top_loss_themes', [])
        import_record.top_win_themes = result.get('top_win_themes', [])
        import_record.competitor_patterns = result.get('competitor_patterns', {})
        import_record.processed_at = datetime.now(timezone.utc)

        db.commit()

        # Mark job success
        queue_service.mark_success(job_id, {
            'import_id': import_id,
            'deal_insights_count': len(result.get('deal_insights', [])),
            'support_insights_count': len(result.get('support_insights', [])),
            'deals_analyzed': result.get('deals_analyzed', 0),
            'activities_analyzed': result.get('activities_analyzed', 0)
        })

        return {
            'status': 'completed',
            'import_id': import_id,
            'deal_insights': len(result.get('deal_insights', [])),
            'support_insights': len(result.get('support_insights', []))
        }

    except Exception as e:
        error_msg = str(e)
        error_tb = traceback.format_exc()
        print(f"[activity_insight_task] Error for job {job_id}: {error_msg}")

        if db:
            try:
                queue_service = QueueService(db)
                queue_service.mark_failure(job_id, error_msg, error_tb)

                # Update import record status
                input_data = queue_service.get_job(job_id).input_data or {}
                import_id = input_data.get('import_id')
                if import_id:
                    from app.models.activity_insights import ActivityImport
                    import_record = db.query(ActivityImport).filter(
                        ActivityImport.id == import_id
                    ).first()
                    if import_record:
                        import_record.status = "failed"
                        import_record.error_message = error_msg
                        db.commit()
            except Exception:
                pass

        raise

    finally:
        if db:
            db.close()
