# Feature Voting System - Claude Code Instructions

## Code Conventions

### Process (always follow)
Before writing code that references existing models or services:
1. Read the model/service definition file to verify exact field/method names
2. Check imports at top of the file being edited to see what's already available
3. Look at similar existing code in the same file for patterns to follow

### Quick Reference (update when changing these)
Common patterns - verify against source if unsure:

**Models** (`backend/app/models/`):
- Product: `CIProduct` → `product_name`, `product_description`, `product_category`
- Competitor: `ProductCompetitor` → `competitor_name`, `competitor_url`, `deep_analysis_enabled`
- Feature: `ProductFeature` → `feature_name`, `feature_description`
- Report: `CompetitorFunctionalReport`, `LandscapeOpportunityReport`

**Services** (`backend/app/services/`):
- `QueueService` → `mark_running()`, `mark_success()`, `mark_failure()`, `get_job()`

**Celery Tasks** (`backend/app/queue/tasks.py`):
- Use `@shared_task` decorator (not `@celery_app.task`)
- Import models inside task functions to avoid circular imports

**When to update this section:**
- Adding/renaming model fields
- Adding/renaming service methods
- Changing patterns used in 3+ places

## Project Structure

- `backend/` - FastAPI backend with SQLAlchemy models
- `frontend/` - React TypeScript frontend
- `docs/development/` - Design documents and prompts

## Development Commands

```bash
# Backend
cd backend && ./venv/bin/python -m uvicorn app.main:app --reload --port 8000

# Celery worker
cd backend && ./venv/bin/celery -A app.queue worker --loglevel=info --pool=solo

# Frontend
cd frontend && npm run dev
```
