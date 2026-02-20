# VoteFlow Testing Plan

## Current Test Inventory

**14 test files | 212 passing tests | 0 failures**

### Test Files

| Test File | What It Covers | Tests | Status |
|-----------|---------------|-------|--------|
| `test_api_auth.py` | Registration, login, JWT, RBAC, account mgmt, password reset/change, security utils | 52 | **P0 Complete** |
| `test_api_ideas.py` | Ideas CRUD, filtering, review/publish workflow, comments, auth/permissions | 24 | **P0 Complete** |
| `test_api_competitive_agents.py` | Config CRUD, competitor mgmt, V2 analysis triggers, landscape synthesis | 18 | **P0 Complete** |
| `test_api_products.py` | Product CRUD, analyze, discover competitors, features, permissions | 17 | **P0 Complete** |
| `test_scheduled_execution.py` | Scheduler: next_run calculations, check_scheduled_tasks dispatch, Celery Beat config | 17 | Pre-existing |
| `test_phase1_queue.py` | QueueJob model + QueueService: CRUD, status transitions, UUID generation, cancellation | 14 | Pre-existing |
| `test_ci_models.py` | CI models: CIProduct, relationships, constraints, cascade deletes, permissions | 12 | Pre-existing |
| `test_api_synthesis.py` | Synthesis status, trigger runs, list/get runs, source data validation | 11 | **P0 Complete** |
| `test_base_agent.py` | BaseAgent framework: execution, retry logic, JSON parsing, error handling | 11 | Pre-existing |
| `test_llm_service_extended.py` | LLMService: agent calls, retry logic, token counting, API error handling | 10 | Pre-existing |
| `test_agent_centric_integration.py` | V2 architecture: config flow, V2 dispatch, component importability | 9 | Pre-existing |
| `test_api_submissions.py` | Idea structuring, submission with auto-triage, auth/validation | 8 | **P0 Complete** |
| `test_api_votes.py` | Cast vote, duplicate prevention, vote counting, auth | 6 | **P0 Complete** |
| `test_product_analyzer.py` | ProductAnalyzerAgent: execution, output schema validation | 3 | Pre-existing |
| `conftest.py` | Shared fixtures: DB session, TestClient, auth helpers, test data | — | Infrastructure |

---

## Coverage Map

### By Module Category

| Category | Files With Tests | Total Files | Coverage |
|----------|-----------------|-------------|----------|
| API Endpoints | 7 / 11 | 64% | `auth`, `ideas`, `votes`, `submissions`, `products`, `competitive_agents`, `synthesis` |
| Agents | 2 / 11 | 18% | `base_agent`, `product_analyzer` |
| Celery Tasks | 2 / 14 | 14% | `check_scheduled_tasks`, `run_competitive_analysis_v2` (dispatch only) |
| Services | 2 / 20 | 10% | `QueueService`, `LLMService` (partial) |
| Models | 3 / 15 | 20% | CI models, QueueJob, CompetitiveAgentConfig (integration) |

### Detailed Source-to-Test Mapping

#### Agents (`backend/app/agents/`)

| Agent | Test Status | Notes |
|-------|-------------|-------|
| `BaseAgent` | **Tested** | Comprehensive (11 tests) |
| `ProductAnalyzerAgent` | **Tested** | Basic execution (3 tests) |
| `CompetitorResearcherAgent` | Not tested | Discovery + differential analysis |
| `DifferentialAnalysisAgent` | Not tested | Nested in competitor_researcher.py |
| `FeatureExtractorAgent` | Not tested | Feature extraction from competitor pages |
| `FeatureDetailExpanderAgent` | Not tested | Feature detail enrichment |
| `IdeaStructuringAgent` | Not tested | Raw text → structured idea |
| `IdeaTriageAgent` | Not tested | Dedup, scoring, auto-accept logic |
| `CompetitorFunctionalAuditAgent` | Not tested | V2 functional audit pipeline |
| `LandscapeOpportunitySynthesizerAgent` | Not tested | V2 landscape synthesis |
| `OpportunitySynthesisAgent` | Not tested | Cross-source synthesis |
| `InternalDiscoveryAgent` | Not tested | Win/loss + support theme extraction |
| `ActivityInsightAgent` | Not tested | CRM activity analysis |

#### Celery Tasks (`backend/app/queue/tasks.py`)

| Task | Test Status | Notes |
|------|-------------|-------|
| `check_scheduled_tasks` | **Tested** | Comprehensive (12 tests) |
| `run_competitive_analysis_v2` | **Partial** | Dispatch tested, not execution |
| `analyze_product_task` | Not tested | |
| `discover_competitors_task` | Not tested | |
| `normalize_idea_task` | Not tested | |
| `triage_idea_task` | Not tested | |
| `submit_and_triage_idea_task` | Not tested | |
| `functional_audit_task` | Not tested | V2 pipeline |
| `landscape_synthesis_task` | Not tested | V2 pipeline |
| `aggregate_functional_audits` | Not tested | V2 chord callback |
| `internal_discovery_task` | Not tested | |
| `activity_insight_task` | Not tested | |
| `opportunity_synthesis_task` | Not tested | |
| `health_check` | Not tested | |

#### API Endpoints (`backend/app/api/`)

| Endpoint File | Routes | Test Status |
|---------------|--------|-------------|
| `auth.py` | POST /register, /login, GET /me, /users, PATCH /users/{id}/role, POST /password/reset/change | **Tested** (52 tests) |
| `ideas.py` | POST/GET /ideas, /ideas/{id}, /submit, /from-feature, /pending-review, /review, /publish, /comments | **Tested** (24 tests) |
| `competitive_agents.py` | GET/PUT /config, POST /competitors, /run-v2, /landscape-synthesis, GET /landscape-report | **Tested** (18 tests) |
| `products.py` | POST/GET/PATCH/DELETE /products, /analyze, /features, /discover | **Tested** (17 tests) |
| `synthesis.py` | GET /status, POST /run, GET /runs, /runs/{id} | **Tested** (11 tests) |
| `submissions.py` | POST /submissions/structure, /submit | **Tested** (8 tests) |
| `votes.py` | POST /ideas/{id}/vote | **Tested** (6 tests) |
| `internal_feedback.py` | POST /import, GET /imports, /themes, POST /activity/import, GET /activity/insights | Not tested |
| `pm_review.py` | GET /queue, /queue/{id}, /stats, POST /assign, /approve, /reject, /batch/approve | Not tested |
| `monitoring.py` | GET/PUT /config/{id}, POST /enable, GET /snapshots | Not tested |
| `admin.py` | GET /costs/summary, /costs/user, /costs/product, GET/POST/PUT /idea-lifecycle-statuses | Not tested |

#### Services (`backend/app/services/`)

| Service | Test Status | Notes |
|---------|-------------|-------|
| `QueueService` | **Tested** | CRUD operations (9 tests) |
| `LLMService` | **Partial** | call_agent + retry tested; structure_idea legacy only |
| `VectorService` | Not tested | Embedding storage + similarity search |
| `SimilarityDetectorService` | Not tested | Idea dedup, feature matching |
| `IdeaGenerationService` | Not tested | |
| `IdeaNormalizerService` | Not tested | |
| `PermissionService` | Not tested | |
| `ProductService` | Not tested | |
| `SessionService` | Not tested | |
| `PMReviewService` | Not tested | |
| `CostTrackingService` | Not tested | |
| `CompetitorIntelligenceService` | Not tested | |
| `SearchService` | Not tested | |
| `DocumentParsingService` | Not tested | |
| `HTMLCleanerService` | Not tested | |
| `ActivityParserService` | Not tested | |
| `InternalThemeMergerService` | Not tested | |
| `PromptLoaderService` | Not tested | |
| `ReportExportService` | Not tested | |
| `CostCalculator` | Not tested | |

#### Models (`backend/app/models/`)

| Model File | Test Status | Notes |
|------------|-------------|-------|
| `competitor_intelligence.py` | **Tested** | Comprehensive (12 tests) |
| `queue.py` | **Tested** | Enums + model (5 tests) |
| `competitive_agent.py` | **Partial** | Config creation/update via integration tests |
| `idea.py` | Not tested | Core model — Idea, IdeaStatus, SourceType |
| `vote.py` | Not tested | |
| `user.py` | Not tested | Created in fixtures but not tested |
| `submission.py` | Not tested | |
| `competitive_reports.py` | Not tested | FunctionalReport, LandscapeReport, CompetitorAlert |
| `synthesis.py` | Not tested | SynthesisRun, SynthesizedOpportunity |
| `internal_feedback.py` | Not tested | FeedbackImport, WinLossTheme, SupportTheme |
| `activity_insights.py` | Not tested | ActivityImport, DealInsight, SupportInsight |
| `pm_review.py` | Not tested | PMReviewQueue, CompetitorSnapshot, MonitoringConfig |
| `cost_tracking.py` | Not tested | LLMUsageLog |
| `idea_lifecycle_status.py` | Not tested | |
| `idea_comment.py` | Not tested | |
| `idea_status_history.py` | Not tested | |
| `password_reset.py` | Not tested | |

---

## Completed Test Categories

### Category 1A: Authentication & Security Tests — COMPLETE (52 tests)

**Test file**: `test_api_auth.py`

| Section | Tests | What's Covered |
|---------|-------|----------------|
| Security Utilities | 7 | `hash_password`, `verify_password`, `create_access_token` (default/custom expiry) |
| Registration | 5 | Happy path, duplicate email/username, missing fields, default role |
| Login | 6 | Username/email login, wrong password, nonexistent user, inactive user, token claims |
| Token & Session | 5 | Valid/expired/malformed/missing token, token for deleted user |
| RBAC | 7 | Admin-only/PO-or-admin endpoint enforcement, user listing, role changes, self-role prevention |
| Account Management | 5 | Deactivate/reactivate user, deactivated login blocked, self-deactivation prevention, nonexistent user |
| Password Reset | 10 | OTP generation, email non-enumeration, valid/expired/used/wrong OTP, OTP invalidation |
| Password Change | 7 | Happy path, wrong current password, same password, weak password, auth required |

### Category 1B: API Endpoint Tests — COMPLETE (84 tests)

| Test File | Tests | What's Covered |
|-----------|-------|----------------|
| `test_api_ideas.py` | 24 | CRUD, filtering by status/product, review/publish workflow, comments, permissions |
| `test_api_competitive_agents.py` | 18 | Config CRUD, competitor management, V2 analysis triggers, landscape synthesis |
| `test_api_products.py` | 17 | Product CRUD, analyze, discover competitors, features, permissions |
| `test_api_synthesis.py` | 11 | Status check, trigger synthesis, list/get runs, source data validation |
| `test_api_submissions.py` | 8 | Idea structuring, submission with auto-triage, auth/validation |
| `test_api_votes.py` | 6 | Cast vote, duplicate prevention, vote counting, auth |

**Patterns covered across all API tests**:
- Authentication/authorization on every endpoint
- Input validation (missing fields, bad types, invalid IDs)
- Correct HTTP status codes (200, 201, 400, 401, 403, 404)
- Response shape matches frontend expectations

---

## Remaining Test Categories

### Category 2: Core Model Tests

**Why**: Idea, Vote, User, and Submission are foundational. Broken model behavior cascades everywhere.

| Test File | Models | Est. Tests |
|-----------|--------|------------|
| `test_idea_model.py` | Idea CRUD, status transitions, source types, to_dict, relationships | 10-12 |
| `test_vote_model.py` | Vote creation, unique constraints, user-idea relationship | 5-6 |
| `test_user_model.py` | User creation, role enum, password hashing, product access | 6-8 |
| `test_report_models.py` | CompetitorFunctionalReport, LandscapeOpportunityReport, CompetitorAlert | 8-10 |
| `test_synthesis_models.py` | SynthesisRun, SynthesizedOpportunity, status transitions | 6-8 |

### Category 3: V2 Pipeline Task Tests

**Why**: The V2 competitive analysis pipeline is the differentiating feature. Tasks are currently untested beyond dispatch.

| Test File | Tasks | Est. Tests |
|-----------|-------|------------|
| `test_v2_pipeline_tasks.py` | `functional_audit_task`, `aggregate_functional_audits`, `landscape_synthesis_task`, `run_competitive_analysis_v2` (full execution) | 12-15 |
| `test_idea_pipeline_tasks.py` | `normalize_idea_task`, `triage_idea_task`, `submit_and_triage_idea_task` | 8-10 |
| `test_product_tasks.py` | `analyze_product_task`, `discover_competitors_task` | 6-8 |

**Key patterns to test**:
- Task creates QueueJob and marks running/success/failure correctly
- Task handles missing products, missing competitors gracefully
- Task calls the right agent with correct inputs
- Task stores results in correct models

### Category 4: Critical Service Tests

**Why**: Services contain business logic that multiple API endpoints and tasks depend on.

| Test File | Services | Est. Tests |
|-----------|----------|------------|
| `test_idea_normalizer_service.py` | Normalization pipeline, field extraction, duplicate handling | 8-10 |
| `test_similarity_detector.py` | Similar idea detection, feature matching, urgency scoring | 8-10 |
| `test_cost_tracking_service.py` | Usage logging, cost calculation, summary aggregation | 6-8 |
| `test_permission_service.py` | Access checks, role validation, product permissions | 6-8 |

### Category 5: Remaining Agent Tests

**Why**: Agents contain LLM interaction patterns. Testing validates prompt → output schema contracts.

| Test File | Agents | Est. Tests |
|-----------|--------|------------|
| `test_competitor_researcher.py` | CompetitorResearcherAgent, DifferentialAnalysisAgent | 6-8 |
| `test_functional_audit_agent.py` | CompetitorFunctionalAuditAgent | 4-6 |
| `test_landscape_synthesizer_agent.py` | LandscapeOpportunitySynthesizerAgent | 4-6 |
| `test_idea_agents.py` | IdeaTriageAgent, IdeaStructuringAgent | 6-8 |
| `test_synthesis_agent.py` | OpportunitySynthesisAgent | 4-5 |

**Key patterns to test**:
- Output matches Pydantic schema
- Handles empty/malformed LLM responses
- Correct prompt construction with product/competitor context

---

## Priority Order

| Priority | Category | Rationale |
|----------|----------|-----------|
| **P0** | Auth & Security Tests (1A) | Security boundary; zero coverage on registration, login, JWT, RBAC, password reset |
| **P0** | API Endpoint Tests (1B) | Zero coverage on public interface; highest regression risk |
| **P1** | Core Model Tests | Foundation for all features; validates data integrity |
| **P2** | V2 Pipeline Task Tests | Core differentiating feature; complex multi-step orchestration |
| **P3** | Critical Service Tests | Business logic reused across endpoints and tasks |
| **P4** | Remaining Agent Tests | LLM contract validation; lower risk since BaseAgent is well-tested |

---

## Test Infrastructure

**Shared fixtures** (in `conftest.py`):
- `db_session` — In-memory SQLite with `StaticPool` (shares DB across threads), creates all tables
- `client` — FastAPI `TestClient` with DB dependency override and rate limiting disabled
- `mock_llm_service` — Mocked Anthropic client
- `voter_user` / `admin_user` / `po_user` — Users with hashed passwords for API auth tests
- `test_user` / `test_admin` / `test_po` — Users with plain hashed_password for model tests
- `test_product` — Pre-created CIProduct owned by PO user
- `test_idea` — Pre-created Idea linked to test product
- `auth_headers(user)` — Generates JWT `Authorization` headers for any user

**CI Configuration** (`.github/workflows/ci.yml`):
- Backend: Python 3.11, `pip install -r requirements.txt`, `pytest tests/ -v --tb=short`
- Frontend: Node 20, `npm ci`, `npx tsc --noEmit`, `npm run build`
- Triggered on push/PR to `main`
