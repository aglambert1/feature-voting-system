# Testing Summary - Quick Reference

## What Testing Exists

### Backend Tests (6 files)

| File | Command | Time | What it Tests |
|------|---------|------|---------------|
| `test_schemas.py` | `python test_schemas.py` | ~1s | Schema validation only |
| `test_api.py` | `python test_api.py` | ~10s | **Auth only** (register, login, JWT, admin) |
| `test_complete_api.py` | `python test_complete_api.py` | ~20s | **ALL endpoints** (auth, ideas, votes, submissions) |
| `test_llm_service.py` | `python test_llm_service.py` | ~5s | AI/LLM service |
| `test_chunk2_api.sh` | `./test_chunk2_api.sh` | ~5s | Ideas & votes (bash) |
| `test_chunk3_api.sh` | `./test_chunk3_api.sh` | ~10s | Submissions (bash) |

### Frontend Tests

| Test | Command | Purpose |
|------|---------|---------|
| Lint | `npm run lint` | Code quality |
| Build | `npm run build` | Production bundle |
| Manual | Open http://localhost:5173 | User flow testing |

**Note:** No automated frontend tests exist yet (no .test.js/.spec.js files)

---

## Quick Test Commands

### Backend - Schema Tests (Fastest)
```bash
cd backend
source venv/bin/activate
python test_schemas.py
```
**No dependencies needed** - tests Pydantic schemas only

### Backend - Complete API Tests (RECOMMENDED)
```bash
# Start server first
./start.sh

# In new terminal
cd backend
source venv/bin/activate
python test_complete_api.py
```
Tests: **ALL endpoints** - auth, ideas, votes, submissions, security

### Backend - Auth Only Tests
```bash
cd backend
source venv/bin/activate
python test_api.py
```
Tests: registration, login, JWT, admin access (auth endpoints only)

### Backend - Ideas & Voting
```bash
# Server must be running
cd backend
./test_chunk2_api.sh
```
Tests: create ideas, vote, vote counts

### Backend - AI Submissions
```bash
# Server must be running + API key configured
cd backend
./test_chunk3_api.sh
```
Tests: AI structuring, submissions, tracking

### Frontend - Lint
```bash
cd frontend
npm run lint
```

### Frontend - Build
```bash
cd frontend
npm run build
```

---

## Testing New Backend Components

### Option 1: Python Script (Simple)

Create `backend/test_my_feature.py`:
```python
#!/usr/bin/env python3
import requests

BASE_URL = "http://localhost:8000"

# Login first (if needed)
login = requests.post(f"{BASE_URL}/auth/login",
    data={"username": "test", "password": "test123"})
token = login.json()["access_token"]

# Test your endpoint
response = requests.get(
    f"{BASE_URL}/my-endpoint",
    headers={"Authorization": f"Bearer {token}"}
)

if response.status_code == 200:
    print("✓ Test passed!")
else:
    print(f"✗ Test failed: {response.status_code}")
```

**Run:**
```bash
cd backend
source venv/bin/activate
python test_my_feature.py
```

### Option 2: Bash Script (Quick)

Create `backend/test_my_feature.sh`:
```bash
#!/bin/bash
BASE_URL="http://localhost:8000"

echo "Testing my feature..."

RESPONSE=$(curl -s "${BASE_URL}/my-endpoint")

if echo "$RESPONSE" | grep -q "expected"; then
    echo "✓ Passed"
else
    echo "✗ Failed"
fi
```

**Run:**
```bash
cd backend
chmod +x test_my_feature.sh
./test_my_feature.sh
```

### Option 3: pytest (Professional)

Create `backend/tests/test_my_feature.py`:
```python
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_my_endpoint():
    response = client.get("/my-endpoint")
    assert response.status_code == 200
```

**Run:**
```bash
cd backend
source venv/bin/activate
pytest tests/ -v
```

---

## Testing Frontend Components

### Currently Available

1. **Linting:** `npm run lint`
2. **Build:** `npm run build`
3. **Manual:** Browser testing at http://localhost:5173

### To Add Automated Tests (Future)

```bash
cd frontend
npm install -D vitest @testing-library/react @testing-library/jest-dom
```

Create `frontend/src/components/__tests__/MyComponent.test.jsx`:
```javascript
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import MyComponent from '../MyComponent'

describe('MyComponent', () => {
  it('renders correctly', () => {
    render(<MyComponent />)
    expect(screen.getByText('Expected Text')).toBeInTheDocument()
  })
})
```

---

## Manual Testing Frontend

### Full User Flow

1. **Register:** http://localhost:5173 → Register
2. **Login:** Use credentials
3. **View Ideas:** Check list loads
4. **Submit Idea:** Test AI structuring
5. **Vote:** Test upvote/downvote
6. **Logout:** Verify token cleared

### Browser DevTools

```javascript
// Check auth in console
localStorage.getItem('token')

// Check API calls in Network tab
// Filter: XHR/Fetch

// Check React components in React DevTools
```

---

## Using Swagger UI

**Best for quick API testing:**

1. Open: http://localhost:8000/docs
2. Find your endpoint
3. Click "Try it out"
4. Fill in parameters
5. Execute
6. View response

**Example - Test registration:**
- Expand `POST /auth/register`
- Click "Try it out"
- Enter:
  ```json
  {
    "username": "newuser",
    "email": "new@test.com",
    "password": "pass123",
    "full_name": "New User"
  }
  ```
- Click "Execute"

---

## Test Coverage

### Backend - Well Tested ✅

- ✅ Schema validation (test_schemas.py)
- ✅ Authentication flow (test_api.py)
- ✅ JWT tokens (test_api.py)
- ✅ Role-based access (test_api.py)
- ✅ Ideas CRUD (test_chunk2_api.sh)
- ✅ Voting system (test_chunk2_api.sh)
- ✅ AI structuring (test_llm_service.py)
- ✅ Submissions tracking (test_chunk3_api.sh)

### Frontend - Manual Only ⚠️

- ⚠️ No automated component tests
- ⚠️ No integration tests
- ✅ Linting configured
- ✅ Build validation works
- ⚠️ Manual browser testing required

---

## When to Run Tests

### Before Committing
```bash
# Quick check
cd backend && source venv/bin/activate && python test_schemas.py
cd frontend && npm run lint
```

### Before PR/Merge
```bash
# Full backend tests
./start.sh  # Terminal 1

# Terminal 2
cd backend && source venv/bin/activate
python test_api.py
./test_chunk2_api.sh

# Frontend
cd frontend
npm run lint
npm run build
```

### After Breaking Changes
- Run all tests
- Manual browser testing
- Check all user flows

---

## Test Data

### Default Test Users

From `test_api.py`:
- Username: `demouser`
- Password: `SecurePassword123`
- Email: `demo@example.com`

From `test_chunk2_api.sh`:
- Username: `chunk2user`
- Password: `SecurePass123`

From `test_chunk3_api.sh`:
- Username: `chunk3user`
- Password: `SecurePass123`

### Reset Test Data

```bash
cd backend
rm feature_voting.db
# Restart server - DB will be recreated
```

---

## Troubleshooting

### "Connection refused"
```bash
# Start servers
./start.sh

# Or check if running
curl http://localhost:8000/health
```

### "Module not found"
```bash
cd backend
source venv/bin/activate
```

### "Database locked"
```bash
# Stop all servers
pkill -f uvicorn
pkill -f vite

# Restart
./start.sh
```

---

## Documentation Links

- Full Testing Guide: [TESTING_GUIDE.md](./TESTING_GUIDE.md)
- API Documentation: http://localhost:8000/docs
- Quick Reference: [QUICK_REFERENCE.md](./QUICK_REFERENCE.md)
- Scripts Documentation: [SCRIPTS_README.md](./SCRIPTS_README.md)

---

**Created:** 2025-10-31
