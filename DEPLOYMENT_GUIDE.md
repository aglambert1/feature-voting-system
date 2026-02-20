# Deployment & CI/CD Guide

## Domain Setup

### When Do You Need a Custom Domain?

| Phase | Domain Needed? | What to Use |
|-------|---------------|-------------|
| Friends & Family | No | Render's free subdomain (`your-app.onrender.com`) |
| Private Beta | Optional | Free subdomain works; custom domain adds polish |
| Paid Beta / Public | Yes | Custom domain required for trust and branding |

### Domain Setup Process (~30 minutes)

1. **Purchase domain** (~$10-15/year)
   - Recommended registrars: Namecheap, Cloudflare, Porkbun
   - Avoid: GoDaddy (upsells), Google Domains (now Squarespace)

2. **Configure DNS**
   - Add CNAME record pointing to your Render URL
   - Example: `app.yourdomain.com` → `your-app.onrender.com`

3. **Add to Render**
   - Dashboard → Your Service → Settings → Custom Domain
   - Enter your domain
   - Render provisions SSL automatically (free, via Let's Encrypt)

4. **Wait for propagation** (5 min to 48 hours, usually <1 hour)

---

## Render CI/CD

### How Automatic Deployments Work

```
Push to GitHub main → Render detects → Builds → Deploys
        ↓                                    ↓
    (2-5 min)                         (zero downtime)
```

### Setup Steps

1. **Connect GitHub repo to Render**
   - Render Dashboard → New → Web Service
   - Select your repo and branch (usually `main`)

2. **Configure build settings**
   ```
   Build Command: pip install -r requirements.txt
   Start Command: uvicorn app.main:app --host 0.0.0.0 --port $PORT
   ```

3. **Set environment variables**
   - Dashboard → Your Service → Environment
   - Add: `SECRET_KEY`, `DATABASE_URL`, `ANTHROPIC_API_KEY`, etc.

4. **Enable auto-deploy**
   - Settings → Auto-Deploy → Yes (default)

### What Happens During Deploy

1. Render detects push to watched branch
2. Spins up new container, runs build command
3. Starts new version alongside old version
4. Health check: hits your app's root endpoint
5. If healthy → switches traffic to new version
6. If unhealthy → keeps old version running (no downtime)

### Database Migrations

**Option A: Manual (recommended for now)**
```bash
# After deploy, run via Render Shell
alembic upgrade head
```

**Option B: Auto-run on deploy**
```bash
# Build command (runs migrations before start)
pip install -r requirements.txt && alembic upgrade head
```

⚠️ **Warning:** Destructive migrations (dropping columns) can break the old version during rolling deploy. For these:
1. Deploy code that handles both old and new schema
2. Run migration
3. Deploy code that only uses new schema

### Rollback

If something breaks:
1. Render Dashboard → Deploys
2. Find the last working deploy
3. Click → Rollback
4. ~30 seconds to restore

---

## Testing Strategy

### Current State

You have:
- pytest configured with markers (`slow`, `integration`, `unit`)
- ~15 test files covering models, services, API
- Manual testing before merge

### Recommended Testing by Phase

| Phase | Approach | Effort |
|-------|----------|--------|
| **Development (now)** | Manual + local pytest | Current |
| **Private Beta** | Add CI smoke tests | 2-4 hours |
| **Paid Beta** | CI required + critical path tests | 1-2 days |
| **Scale** | Add E2E, performance tests | Future |

### Phase 1: Add CI Smoke Tests (Before Beta)

Create `.github/workflows/test.yml`:

```yaml
name: Tests

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        working-directory: ./backend
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-asyncio

      - name: Run unit tests
        working-directory: ./backend
        run: pytest -m "not integration and not slow" --tb=short
        env:
          DATABASE_URL: sqlite:///./test.db
          SECRET_KEY: test-secret-key-for-ci
          DEBUG: "false"
```

This gives you:
- Tests run on every push and PR
- Blocks merge if tests fail
- ~2-5 min CI time

### Phase 2: Critical Path Tests (Before Paid)

Add tests for revenue-critical flows:

```python
# backend/tests/test_critical_paths.py

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

class TestCriticalPaths:
    """Tests for flows that must never break."""

    def test_health_check(self):
        """App starts and responds."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_auth_flow(self):
        """User can register and login."""
        # Register
        response = client.post("/auth/register", json={
            "email": "test@example.com",
            "password": "testpassword123"
        })
        assert response.status_code in [200, 201, 409]  # 409 if exists

        # Login
        response = client.post("/auth/login", data={
            "username": "test@example.com",
            "password": "testpassword123"
        })
        assert response.status_code == 200
        assert "access_token" in response.json()

    def test_idea_creation(self, auth_headers):
        """Authenticated user can create idea."""
        response = client.post("/ideas", json={
            "title": "Test Idea",
            "description": "Test description"
        }, headers=auth_headers)
        assert response.status_code in [200, 201]

    def test_product_creation(self, auth_headers):
        """User can create product for analysis."""
        response = client.post("/products", json={
            "name": "Test Product",
            "description": "Test description"
        }, headers=auth_headers)
        assert response.status_code in [200, 201]
```

### What You Can Skip (For Now)

- **Full code coverage requirements** — Focus on critical paths, not %
- **E2E browser tests** — Manual testing is fine at low scale
- **Performance/load testing** — Not needed until you have load
- **Visual regression tests** — Overkill for beta

### Post-Deploy Smoke Test

Add a simple health check endpoint if you don't have one:

```python
# app/api/health.py
from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
async def health_check():
    return {"status": "healthy"}
```

Render can use this for health checks during deploy.

---

## Deployment Checklist

### Before First Deploy

- [ ] Security fixes applied (see SECURITY_FIXES_PROMPT.md)
- [ ] Environment variables documented in `.env.example`
- [ ] `.env` is gitignored
- [ ] Database migration strategy decided
- [ ] Health check endpoint exists

### Render Setup

- [ ] Create Render account
- [ ] Connect GitHub repo
- [ ] Create Web Service (backend)
- [ ] Create PostgreSQL database
- [ ] Create Redis instance (for Celery)
- [ ] Create Background Worker (Celery)
- [ ] Create Static Site (frontend)
- [ ] Set environment variables
- [ ] Test deploy

### After First Deploy

- [ ] Verify health check passes
- [ ] Test login flow manually
- [ ] Run one competitor analysis
- [ ] Check logs for errors
- [ ] Set up Anthropic billing alerts

---

## Estimated Costs (Render)

| Service | Monthly Cost | Notes |
|---------|-------------|-------|
| Web Service (backend) | $7 | Starter tier |
| Background Worker (Celery) | $7 | Starter tier |
| PostgreSQL | $6 | Starter with backups |
| Redis | $0 | Free tier (25MB) |
| Static Site (frontend) | $0 | Free tier |
| **Infrastructure Total** | **~$20/month** | |
| Anthropic API | $5-50+ | Usage-based |
| Domain | ~$1/month | ($12/year) |
| **Total** | **~$25-75/month** | Depending on usage |
