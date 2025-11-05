# Testing Guide - Feature Voting System

Complete guide to testing both backend and frontend components.

## Table of Contents
- [Backend Testing](#backend-testing)
- [Frontend Testing](#frontend-testing)
- [Integration Testing](#integration-testing)
- [Manual Testing](#manual-testing)

---

## Backend Testing

### Overview

The backend has **5 test files** available:

| Test File | Purpose | Requires API | Requires DB |
|-----------|---------|--------------|-------------|
| `test_schemas.py` | Schema validation | ❌ No | ❌ No |
| `test_llm_service.py` | Claude API integration | ✅ Yes | ❌ No |
| `test_api.py` | Full API endpoints | ✅ Yes | ✅ Yes |
| `test_chunk2_api.sh` | Ideas & votes flow | ✅ Yes | ✅ Yes |
| `test_chunk3_api.sh` | Submissions flow | ✅ Yes | ✅ Yes |

### 1. Schema Validation Tests

**What it tests:** Pydantic schema validation (no server needed)

**Tests:**
- ✓ IdeaCreate schema validation
- ✓ VoteCreate schema validation
- ✓ SubmissionStructureRequest/Response schemas
- ✓ VoteCount schema
- ✓ Invalid input rejection

**Run:**
```bash
cd backend
source venv/bin/activate
python test_schemas.py
```

**Expected output:**
```
============================================================
Testing Pydantic Schemas (Chunk 1)
============================================================

Test 1: IdeaCreate Schema
✓ Valid idea created
...
All Schema Tests Passed! ✓
```

**When to use:**
- Testing schema changes
- Verifying validation rules
- Quick sanity checks (no dependencies)

---

### 2. LLM Service Tests

**What it tests:** Claude API integration for structuring ideas

**Prerequisites:**
- ANTHROPIC_API_KEY in `.env`
- Internet connection

**Tests:**
- ✓ Simple feature request structuring
- ✓ Complex feature description structuring
- ✓ API key validation
- ✓ Response format validation

**Run:**
```bash
cd backend
source venv/bin/activate
python test_llm_service.py
```

**Expected output:**
```
============================================================
Testing LLM Service (Claude API)
============================================================

✓ API key configured: sk-ant-api03-xxxxx...

Test 1: Simple Feature Request
⏳ Calling Claude API...
✓ Success! (took 2.3s)

Structured Output:
  Title: Dark Mode Toggle
  What:  A toggle switch in settings that enables dark mode...
...
```

**When to use:**
- Testing Claude API integration
- Verifying idea structuring logic
- Testing AI response parsing

---

### 3. Full API Endpoint Tests

**What it tests:** All authentication and user management endpoints

**Prerequisites:**
- Backend server running at http://localhost:8000
- Database initialized

**Tests:**
- ✓ Health check endpoint
- ✓ User registration
- ✓ User login
- ✓ Protected routes with JWT
- ✓ Security (unauthorized access rejection)
- ✓ Admin login
- ✓ Admin-only endpoints
- ✓ Role-based access control

**Run:**
```bash
# Terminal 1: Start backend
cd backend
source venv/bin/activate
uvicorn app.main:app --reload

# Terminal 2: Run tests
cd backend
source venv/bin/activate
python test_api.py
```

**Or with servers already running:**
```bash
# If ./start.sh is running
cd backend
source venv/bin/activate
python test_api.py
```

**Expected output:**
```
============================================================
Testing Feature Voting System API
============================================================

1. Testing health check endpoint...
Status: 200
{'message': 'Healthy', 'status': 'ok'}

2. Registering a new user...
✓ User registered successfully!
...
8. Testing admin-only security...
✓ Security working correctly! Non-admin access denied.

All tests completed!
```

**When to use:**
- Testing authentication flow
- Verifying JWT token handling
- Testing role-based access control
- End-to-end API testing

---

### 4. Ideas & Votes Flow Tests (Bash)

**What it tests:** Complete ideas and voting workflow

**Prerequisites:**
- Backend server running
- Database initialized

**Tests:**
- ✓ User registration
- ✓ User login
- ✓ Create idea (authenticated)
- ✓ List ideas
- ✓ Get single idea
- ✓ Upvote idea
- ✓ Downvote idea
- ✓ Vote count validation

**Run:**
```bash
cd backend
./test_chunk2_api.sh
```

**Expected output:**
```
============================================================
Testing Chunk 2 API Endpoints
============================================================

Test 1: Register new user
✓ User registered successfully

Test 2: Login
✓ Login successful
Token: eyJhbGc...

Test 3: Create idea
✓ Idea created successfully
Idea ID: 5

Test 4: Vote on idea
✓ Vote recorded successfully
Score: 1
...
```

**When to use:**
- Testing ideas CRUD operations
- Testing voting logic
- Testing vote count calculations
- Quick smoke tests

---

### 5. Submissions Flow Tests (Bash)

**What it tests:** AI-powered submission workflow

**Prerequisites:**
- Backend server running
- Database initialized
- ANTHROPIC_API_KEY configured

**Tests:**
- ✓ User registration/login
- ✓ Structure freeform text with AI
- ✓ Submit structured idea
- ✓ Link submission to idea
- ✓ Track original vs structured versions

**Run:**
```bash
cd backend
./test_chunk3_api.sh
```

**Expected output:**
```
============================================================
Testing Chunk 3 API Endpoints (Submissions)
============================================================

Test 1: Register and login
✓ User authenticated

Test 2: Structure freeform text
⏳ Calling AI...
✓ Text structured successfully
Title: Dark Mode Feature

Test 3: Submit structured idea
✓ Idea submitted with tracking
Idea ID: 10
Submission ID: 5
...
```

**When to use:**
- Testing AI integration
- Testing submission tracking
- Verifying idea-submission linking
- End-to-end submission flow

---

### Writing New Backend Tests

#### Option 1: Using pytest (Recommended for new tests)

Create `backend/tests/test_your_feature.py`:

```python
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_your_endpoint():
    """Test your new endpoint."""
    response = client.get("/your-endpoint")
    assert response.status_code == 200
    assert "expected_key" in response.json()

def test_authenticated_endpoint():
    """Test endpoint with authentication."""
    # Login first
    login_response = client.post("/auth/login", data={
        "username": "testuser",
        "password": "testpass"
    })
    token = login_response.json()["access_token"]

    # Use token
    response = client.get(
        "/protected-endpoint",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
```

**Run pytest tests:**
```bash
cd backend
source venv/bin/activate
pytest tests/ -v
```

#### Option 2: Standalone Python Script

Create `backend/test_your_feature.py`:

```python
#!/usr/bin/env python3
import requests

BASE_URL = "http://localhost:8000"

def test_your_feature():
    """Test your new feature."""
    response = requests.get(f"{BASE_URL}/your-endpoint")

    if response.status_code == 200:
        print("✓ Test passed!")
        print(response.json())
    else:
        print(f"✗ Test failed: {response.status_code}")

if __name__ == "__main__":
    test_your_feature()
```

**Run:**
```bash
cd backend
source venv/bin/activate
python test_your_feature.py
```

#### Option 3: Bash Script

Create `backend/test_your_feature.sh`:

```bash
#!/bin/bash
set -e

BASE_URL="http://localhost:8000"

echo "Testing Your Feature"
echo "===================="

# Test endpoint
RESPONSE=$(curl -s "${BASE_URL}/your-endpoint")

if echo "$RESPONSE" | grep -q "expected_value"; then
    echo "✓ Test passed!"
else
    echo "✗ Test failed"
    exit 1
fi
```

**Run:**
```bash
cd backend
chmod +x test_your_feature.sh
./test_your_feature.sh
```

---

## Frontend Testing

### Overview

The frontend currently has **no dedicated test files** but includes:
- ESLint for code quality
- Build validation
- Manual browser testing

### 1. Linting

**What it tests:** Code quality, React best practices, potential bugs

**Run:**
```bash
cd frontend
npm run lint
```

**Expected output:**
```
✓ 0 problems (0 errors, 0 warnings)
```

**Fix issues automatically:**
```bash
npm run lint -- --fix
```

---

### 2. Build Validation

**What it tests:** Production build success, bundle creation

**Run:**
```bash
cd frontend
npm run build
```

**Expected output:**
```
vite v7.1.7 building for production...
✓ 1234 modules transformed.
dist/index.html                   0.45 kB │ gzip:  0.29 kB
dist/assets/index-abc123.css      2.34 kB │ gzip:  1.12 kB
dist/assets/index-def456.js     145.67 kB │ gzip: 46.78 kB
✓ built in 2.34s
```

**Check output:**
```bash
ls -lh dist/
```

---

### 3. Development Server Testing

**What it tests:** Hot reload, dev server functionality

**Run:**
```bash
cd frontend
npm run dev
```

**Test:**
1. Open http://localhost:5173
2. Make a change to a component
3. Save the file
4. Verify changes appear immediately

---

### 4. Manual Browser Testing

**Full flow test:**

1. **Registration:**
   - Open http://localhost:5173
   - Click "Register"
   - Fill in form
   - Submit
   - Verify redirect to login

2. **Login:**
   - Enter credentials
   - Submit
   - Verify redirect to ideas page
   - Check auth token in localStorage

3. **View Ideas:**
   - Check ideas list loads
   - Verify vote counts display
   - Check responsive design

4. **Submit Idea:**
   - Click "Submit Idea"
   - Enter freeform text
   - Click "Structure with AI"
   - Verify structured output appears
   - Edit if needed
   - Submit
   - Verify idea appears in list

5. **Vote on Ideas:**
   - Click upvote button
   - Verify count increases
   - Click downvote button
   - Verify count updates
   - Check can't vote multiple times

6. **Logout:**
   - Click logout
   - Verify redirect to login
   - Verify token removed
   - Verify can't access protected routes

---

### Setting Up Frontend Tests (Future)

The project includes the necessary dependencies but no tests yet. Here's how to add them:

#### Option 1: Add Vitest (Recommended)

**Install:**
```bash
cd frontend
npm install -D vitest @vitest/ui @testing-library/react @testing-library/jest-dom
```

**Create `frontend/vite.config.js`:**
```javascript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.js',
  },
})
```

**Create test file `frontend/src/components/__tests__/IdeaCard.test.jsx`:**
```javascript
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import IdeaCard from '../IdeaCard'

describe('IdeaCard', () => {
  it('renders idea title', () => {
    const idea = {
      id: 1,
      title: 'Test Idea',
      what_description: 'Test description',
      vote_counts: { upvotes: 5, downvotes: 2, score: 3 }
    }

    render(<IdeaCard idea={idea} />)
    expect(screen.getByText('Test Idea')).toBeInTheDocument()
  })
})
```

**Add to package.json:**
```json
{
  "scripts": {
    "test": "vitest",
    "test:ui": "vitest --ui"
  }
}
```

**Run:**
```bash
npm test
```

#### Option 2: Add Jest (Alternative)

```bash
cd frontend
npm install -D jest @testing-library/react @testing-library/jest-dom
```

Follow similar setup as Vitest above.

---

## Integration Testing

### Full Stack Integration Test

**Tests the complete user journey:**

```bash
# Terminal 1: Start both servers
./start.sh

# Terminal 2: Run backend tests
cd backend
source venv/bin/activate
python test_api.py

# Terminal 3: Manual frontend testing
# Open http://localhost:5173 in browser
# Follow manual testing checklist above
```

---

## Manual Testing

### Using Swagger UI

**Best for API exploration:**

1. Start backend: `./start.sh`
2. Open: http://localhost:8000/docs
3. Click any endpoint
4. Click "Try it out"
5. Fill in parameters
6. Click "Execute"
7. View response

**Example: Test user registration:**
1. Expand `POST /auth/register`
2. Click "Try it out"
3. Enter JSON:
   ```json
   {
     "username": "testuser",
     "email": "test@example.com",
     "password": "password123",
     "full_name": "Test User"
   }
   ```
4. Click "Execute"
5. Check response

---

## Testing Checklist

### Before Committing Code

- [ ] Run schema tests: `python test_schemas.py`
- [ ] Run frontend linter: `npm run lint`
- [ ] Run frontend build: `npm run build`
- [ ] Test in browser manually

### Before Deploying

- [ ] Run all backend tests
- [ ] Run frontend build
- [ ] Test full user flow in browser
- [ ] Check error handling
- [ ] Verify security (try accessing protected routes)

### After Adding New Features

- [ ] Write tests for new endpoints
- [ ] Update existing tests if needed
- [ ] Test backward compatibility
- [ ] Update this guide if needed

---

## Common Testing Patterns

### Testing Protected Endpoints

```python
def test_protected_endpoint():
    # 1. Register user
    register_response = requests.post(
        f"{BASE_URL}/auth/register",
        json={"username": "test", "password": "pass123", "email": "test@test.com"}
    )

    # 2. Login
    login_response = requests.post(
        f"{BASE_URL}/auth/login",
        data={"username": "test", "password": "pass123"}
    )
    token = login_response.json()["access_token"]

    # 3. Use token
    response = requests.get(
        f"{BASE_URL}/protected",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
```

### Testing Error Cases

```python
def test_invalid_input():
    response = requests.post(
        f"{BASE_URL}/ideas",
        json={"title": ""}  # Invalid - too short
    )
    assert response.status_code == 422
    assert "validation" in response.json()["detail"][0]["msg"].lower()
```

### Testing Database State

```python
def test_vote_count():
    # Create idea
    idea_id = create_test_idea()

    # Upvote
    upvote(idea_id, token)

    # Check count
    response = requests.get(f"{BASE_URL}/ideas/{idea_id}")
    assert response.json()["vote_counts"]["score"] == 1
```

---

## Quick Reference

### Run All Tests

```bash
# Schema tests (fast, no dependencies)
cd backend && source venv/bin/activate && python test_schemas.py

# API tests (requires running server)
cd backend && source venv/bin/activate && python test_api.py

# Bash tests (requires running server)
cd backend && ./test_chunk2_api.sh && ./test_chunk3_api.sh

# Frontend lint
cd frontend && npm run lint

# Frontend build
cd frontend && npm run build
```

### Test URLs

- Backend API: http://localhost:8000
- Backend Docs: http://localhost:8000/docs
- Frontend App: http://localhost:5173
- Health Check: http://localhost:8000/health

---

## Troubleshooting Tests

### Tests Can't Connect to API
```bash
# Check if backend is running
curl http://localhost:8000/health

# If not, start it
./start.sh
```

### Database Errors
```bash
# Reset database
cd backend
rm feature_voting.db
# Restart backend - DB will be recreated
```

### Import Errors in Tests
```bash
# Ensure venv is activated
cd backend
source venv/bin/activate
python test_api.py
```

### Frontend Build Fails
```bash
# Reinstall dependencies
cd frontend
rm -rf node_modules
npm install
npm run build
```

---

**Created:** 2025-10-31
**Last Updated:** 2025-10-31
