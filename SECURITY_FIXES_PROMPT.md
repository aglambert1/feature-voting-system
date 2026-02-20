# Security Fixes for Production Readiness

## Context
A security audit identified critical vulnerabilities that must be fixed before production deployment. This prompt guides fixing the 5 critical and 5 high-severity issues.

**Note:** These issues are acceptable during local development but MUST be addressed before deploying to any environment accessible from the internet.

---

## When to Apply These Fixes

| Phase | What to Do |
|-------|------------|
| Local development | Current setup is fine — keys are gitignored, DEBUG=true is expected |
| Pre-deployment | Apply all critical fixes (issues 1-5) |
| Production deploy | Apply high-severity fixes (issues 6-10) and set up secrets management |

---

## Critical Issues (Fix Before Deployment)

### 1. Rotate Compromised API Keys
The `.env` file contains real API keys that are committed to git history.

**Action:**
- Rotate Anthropic API key at https://console.anthropic.com
- Rotate Brave Search API key at https://brave.com/search/api/
- Remove `.env` from git history:
  ```bash
  # Install git-filter-repo if needed: pip install git-filter-repo
  git filter-repo --path backend/.env --invert-paths
  ```
- Add `backend/.env` to `.gitignore` if not already present
- Create `backend/.env.example` with placeholder values for documentation

### 2. Remove OTP Bypass Code
**File:** `backend/app/api/auth.py` (around lines 477-505)

Remove the dev bypass that allows OTP `000000`:
```python
# DELETE this block:
if settings.debug and request.otp == settings.dev_otp_bypass:
    is_dev_bypass = True
```

### 3. Remove OTP from API Responses
**File:** `backend/app/api/auth.py` (around lines 425-428)

Remove code that exposes OTP in responses:
```python
# DELETE this block:
if settings.debug and settings.dev_return_otp:
    response.dev_otp = otp
    response.detail = f"[DEV MODE] OTP: {otp} | Expires in 15 minutes..."
```

### 4. Fix JWT Secret Key Default
**File:** `backend/app/config.py` (around line 33)

Change from weak default to required secure value:
```python
# BEFORE:
secret_key: str = "your-secret-key-change-this-in-production"

# AFTER:
secret_key: str = Field(..., min_length=32)  # Required, no default

# Add validation in __init__ or validator:
@validator('secret_key')
def validate_secret_key(cls, v):
    if v == "your-secret-key-change-this-in-production":
        raise ValueError("SECRET_KEY must be changed from default value")
    if len(v) < 32:
        raise ValueError("SECRET_KEY must be at least 32 characters")
    return v
```

Generate a secure key: `python -c "import secrets; print(secrets.token_urlsafe(32))"`

### 5. Remove Auto-Created Admin
**File:** `backend/app/database.py` (around lines 183-243)

Remove or disable the `create_default_admin()` function that auto-creates admin with weak credentials on startup. Instead, provide a CLI command or setup script for manual admin creation.

---

## High Severity Issues

### 6. Fix CORS Configuration
**File:** `backend/app/main.py` (around lines 146-147)

```python
# BEFORE:
allow_methods=["*"],
allow_headers=["*"],

# AFTER:
allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
```

Also ensure `allow_origins` is a specific whitelist, not `["*"]` in production.

### 7. Disable Swagger in Production
**File:** `backend/app/main.py` (around lines 133-134)

```python
# BEFORE:
app = FastAPI(title="Feature Voting API", ...)

# AFTER:
app = FastAPI(
    title="Feature Voting API",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    openapi_url="/openapi.json" if settings.debug else None,
    ...
)
```

### 8. Default DEBUG to False
**File:** `backend/app/config.py` (around line 24)

```python
# BEFORE:
debug: bool = True

# AFTER:
debug: bool = False
```

### 9. Remove Dev OTP Endpoint
**File:** `backend/app/api/auth.py` (around lines 596-670)

Delete the entire endpoint:
```python
# DELETE this entire endpoint:
@router.get("/dev/get-otp/{email}")
async def get_dev_otp(...):
    ...
```

### 10. Add Rate Limiting
Install slowapi and add rate limiting to auth endpoints:

```bash
pip install slowapi
```

```python
# In main.py or auth.py:
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

# Apply to login endpoint:
@router.post("/login")
@limiter.limit("5/minute")
async def login(request: Request, ...):
    ...

# Apply to password reset:
@router.post("/password/reset-request")
@limiter.limit("3/5minutes")
async def reset_request(request: Request, ...):
    ...
```

---

## Verification Checklist

After making changes, verify:

- [ ] App starts with `DEBUG=false`
- [ ] App fails to start with default SECRET_KEY
- [ ] `/docs` and `/redoc` return 404 when `DEBUG=false`
- [ ] OTP `000000` does not bypass verification
- [ ] OTP is not returned in any API response
- [ ] `/auth/dev/get-otp/{email}` returns 404
- [ ] No admin user is auto-created on fresh database
- [ ] Rate limiting blocks excessive login attempts
- [ ] CORS rejects disallowed origins/methods

---

## Environment Variables Needed for Production

```bash
# Required (no defaults)
SECRET_KEY=<generate with: python -c "import secrets; print(secrets.token_urlsafe(32))">
DATABASE_URL=postgresql://user:pass@host:5432/dbname
ANTHROPIC_API_KEY=<your production key>

# Optional
BRAVE_API_KEY=<your production key if using search>
REDIS_URL=redis://host:6379/0
DEBUG=false  # explicitly set
```

---

## Secrets Management for Render/Railway/Fly.io

### Local Development vs Production

**Local development (`backend/.env` — gitignored):**
- Use your real API keys for testing
- DEBUG=true is fine
- Weak SECRET_KEY is acceptable

**Production (Render Environment Variables):**
- Store all secrets in Render dashboard → Service → Environment
- Never commit production keys to code
- Generate a unique SECRET_KEY for production

### Setup Checklist for Deployment

1. **Create `.env.example` for documentation** (commit this):
   ```bash
   # backend/.env.example
   DEBUG=false
   SECRET_KEY=generate-with-secrets-module
   DATABASE_URL=postgresql://user:pass@host:5432/dbname
   ANTHROPIC_API_KEY=your-key-here
   BRAVE_API_KEY=your-key-here
   REDIS_URL=redis://host:6379/0
   ```

2. **Verify `.env` is gitignored:**
   ```bash
   git check-ignore backend/.env  # should output the path
   ```

3. **Add secrets to Render dashboard** (not in code):
   - Go to Render → Your Service → Environment
   - Add each variable with production values
   - Render encrypts at rest and injects at runtime

### Key Rotation Schedule

| Secret | Rotate Every | How |
|--------|--------------|-----|
| ANTHROPIC_API_KEY | 90 days or if leaked | Anthropic Console → Create new key → Update Render → Delete old key |
| SECRET_KEY | 90 days | Generate new → Update Render → Note: logs out all users |
| DATABASE_URL | Managed by Render | Render handles rotation for managed PostgreSQL |

### Leak Prevention

**GitHub Secret Scanning:**
- Enable in GitHub repo → Settings → Security → Secret scanning
- Alerts you if keys are accidentally committed

**Git pre-commit hook** (optional, add to `.git/hooks/pre-commit`):
```bash
#!/bin/sh
if git diff --cached | grep -E "(sk-ant-|ANTHROPIC_API_KEY=sk)" > /dev/null; then
  echo "ERROR: Detected potential API key in commit"
  exit 1
fi
chmod +x .git/hooks/pre-commit
```

**Anthropic usage alerts:**
- Set up billing alerts in Anthropic Console
- Detects unexpected API usage that might indicate a leaked key
