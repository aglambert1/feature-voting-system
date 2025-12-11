# Feature Voting System MVP - Implementation Guide

This guide breaks down the MVP implementation into manageable chunks that can be completed within token limits. Each chunk is self-contained and builds on the previous ones.

---

## Progress Tracker

- [ ] **CHUNK 1**: Backend Schemas & LLM Service
- [ ] **CHUNK 2**: Backend API Endpoints - Ideas & Votes
- [ ] **CHUNK 3**: Backend API Endpoints - Manual Submissions
- [ ] **CHUNK 4**: Frontend Initialization & Setup
- [ ] **CHUNK 5**: Frontend Authentication Pages
- [ ] **CHUNK 6**: Frontend Ideas List & Voting
- [ ] **CHUNK 7**: Frontend Submit Idea Page (AI Flow)
- [ ] **CHUNK 8**: Final Integration & Testing

---

## CHUNK 1: Backend Schemas & LLM Service

**Goal:** Create Pydantic schemas and Claude API integration service

### Files to Create:

1. **`/backend/app/schemas/idea.py`**
   - `IdeaCreate` - For creating new ideas (title, what, why, use_case)
   - `IdeaResponse` - For returning idea data with vote counts
   - `IdeaListResponse` - For listing multiple ideas

2. **`/backend/app/schemas/vote.py`**
   - `VoteCreate` - For casting votes (vote_value: 1 or -1)
   - `VoteResponse` - For returning vote information
   - `VoteCount` - For returning vote statistics

3. **`/backend/app/schemas/submission.py`**
   - `SubmissionStructureRequest` - Freeform text input
   - `SubmissionStructureResponse` - AI-structured output (what, why, use_case)
   - `SubmissionCreate` - Complete submission data
   - `SubmissionResponse` - Submission with tracking info

4. **`/backend/app/services/llm_service.py`**
   - `LLMService` class with methods:
     - `structure_idea(freeform_text: str)` -> dict
   - Uses Anthropic Claude API
   - Handles API errors gracefully
   - Logs API calls for debugging

5. **Update `/backend/app/schemas/__init__.py`**
   - Export all new schemas

### Key Implementation Details:

- Use Pydantic BaseModel for validation
- Include helpful docstrings
- Add Field() validation where needed
- Handle optional fields appropriately
- LLM service should use environment variable for API key

### Testing After Chunk 1:
```bash
# Test that models can be imported
python -c "from app.schemas.idea import IdeaCreate; print('Success')"

# Test LLM service (requires API key in .env)
python -c "from app.services.llm_service import LLMService; service = LLMService(); print('LLM Service initialized')"
```

---

## CHUNK 2: Backend API Endpoints - Ideas & Votes

**Goal:** Create REST API endpoints for ideas and voting

### Files to Create:

1. **`/backend/app/api/ideas.py`**
   - Router with prefix `/ideas`
   - Endpoints:
     - `POST /ideas` - Create new idea
       - Requires authentication
       - Validates input
       - Returns created idea with ID
     - `GET /ideas` - List all active ideas
       - Public endpoint (no auth required)
       - Returns ideas with vote counts
       - Order by score (descending)
     - `GET /ideas/{id}` - Get single idea
       - Public endpoint
       - Returns 404 if not found
       - Includes vote counts

2. **`/backend/app/api/votes.py`**
   - Router with prefix `/votes`
   - Endpoint:
     - `POST /ideas/{idea_id}/vote` - Vote on idea
       - Requires authentication
       - Vote value: 1 (upvote) or -1 (downvote)
       - Upsert logic: create or update existing vote
       - Returns updated vote counts

3. **Update `/backend/app/main.py`**
   - Import new routers
   - Include routers in app:
     ```python
     from app.api import ideas, votes
     app.include_router(ideas.router)
     app.include_router(votes.router)
     ```

### Key Implementation Details:

- Use SQLAlchemy queries with proper joins
- Calculate vote counts efficiently (SUM aggregation)
- Handle one-vote-per-user constraint
- Return proper HTTP status codes (201, 404, etc.)
- Add error handling for database operations

### Testing After Chunk 2:
```bash
# Start the server
uvicorn app.main:app --reload

# Test in browser
# Visit http://localhost:8000/docs
# Try the /ideas endpoints in Swagger UI

# Or use curl
curl http://localhost:8000/ideas
```

---

## CHUNK 3: Backend API Endpoints - Manual Submissions

**Goal:** Create AI-powered submission flow

### Files to Create:

1. **`/backend/app/api/submissions.py`**
   - Router with prefix `/submissions`
   - Endpoints:
     - `POST /submissions/structure` - Structure freeform text
       - Requires authentication
       - Accepts: `{"freeform_text": "..."}`
       - Calls Claude API via LLMService
       - Returns: `{"what": "...", "why": "...", "use_case": "..."}`
       - Tracks timing (how long AI took)
     - `POST /submissions/submit` - Submit structured idea
       - Requires authentication
       - Accepts structured data + original text
       - Creates Idea record
       - Creates Submission record (tracking)
       - Links idea to user
       - Returns created idea with ID

### Key Implementation Details:

- Use async/await for LLM calls
- Add timeout handling (30 seconds max)
- Store original text AND structured version
- Track user edits (compare AI output to final submission)
- Handle LLM API errors gracefully

### Tasks:

1. Create submissions.py endpoint file
2. Install anthropic package:
   ```bash
   cd backend
   source venv/bin/activate
   pip install anthropic
   ```
3. Add API key to `.env`:
   ```
   ANTHROPIC_API_KEY=sk-ant-xxxxx
   ```
4. Update main.py to include submissions router

### Testing After Chunk 3:
```bash
# Test structuring
curl -X POST http://localhost:8000/submissions/structure \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"freeform_text": "I want a dark mode toggle in the settings"}'

# Test submission
curl -X POST http://localhost:8000/submissions/submit \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "original_text": "I want dark mode",
    "title": "Dark Mode Toggle",
    "what_description": "...",
    "why_description": "...",
    "use_case_description": "..."
  }'
```

---

## CHUNK 4: Frontend Initialization & Setup

**Goal:** Set up React project with routing and API client

### Tasks:

1. **Initialize Vite + React Project**
   ```bash
   cd /Users/aglambert/projects/feature-voting-system
   npm create vite@latest frontend -- --template react
   cd frontend
   npm install
   ```

2. **Install Dependencies**
   ```bash
   npm install react-router-dom axios
   npm install -D tailwindcss postcss autoprefixer
   npx tailwindcss init -p
   ```

3. **Configure TailwindCSS**
   - Edit `tailwind.config.js`:
     ```js
     content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"]
     ```
   - Edit `src/index.css`:
     ```css
     @tailwind base;
     @tailwind components;
     @tailwind utilities;
     ```

4. **Create Project Structure**
   ```bash
   mkdir -p src/components
   mkdir -p src/pages
   mkdir -p src/contexts
   mkdir -p src/services
   ```

### Files to Create:

1. **`/frontend/src/services/api.js`**
   - Axios instance with base URL
   - Request interceptor (add auth token)
   - Response interceptor (handle errors)
   - API methods:
     - Auth: `login()`, `register()`, `getCurrentUser()`
     - Ideas: `getIdeas()`, `getIdea(id)`, `createIdea(data)`
     - Votes: `voteOnIdea(ideaId, value)`
     - Submissions: `structureText(text)`, `submitIdea(data)`

2. **`/frontend/src/contexts/AuthContext.jsx`**
   - React Context for auth state
   - Methods: `login()`, `logout()`, `register()`
   - Store token in localStorage
   - Provide current user object
   - Handle token expiration

3. **`/frontend/.env`**
   ```
   VITE_API_URL=http://localhost:8000
   ```

### Testing After Chunk 4:
```bash
# Start frontend dev server
npm run dev

# Visit http://localhost:5173
# Should see default Vite welcome page
```

---

## CHUNK 5: Frontend Authentication Pages

**Goal:** Build login and registration UI

### Files to Create:

1. **`/frontend/src/pages/LoginPage.jsx`**
   - Form with email/username and password
   - Call `login()` from AuthContext
   - Show loading state during submission
   - Show error messages
   - Redirect to /ideas on success
   - Link to register page

2. **`/frontend/src/pages/RegisterPage.jsx`**
   - Form with email, username, password, full_name
   - Call `register()` from AuthContext
   - Show validation errors
   - Show loading state
   - Redirect to /ideas on success
   - Link to login page

3. **`/frontend/src/components/ProtectedRoute.jsx`**
   - Wrapper component for authenticated routes
   - Check if user is logged in
   - Redirect to /login if not authenticated
   - Use React Router's Navigate

4. **`/frontend/src/App.jsx`**
   - Set up React Router
   - Wrap app in AuthProvider
   - Define routes:
     - `/` - Redirect to /ideas
     - `/login` - LoginPage
     - `/register` - RegisterPage
     - `/ideas` - IdeasPage (protected)
     - `/submit` - SubmitIdeaPage (protected)

### Key Implementation Details:

- Use controlled form inputs (useState)
- Basic TailwindCSS styling
- Error handling and validation
- Loading states (disable button while submitting)
- Password field (type="password")

### Testing After Chunk 5:
```bash
# Start both servers:
# Terminal 1: cd backend && uvicorn app.main:app --reload
# Terminal 2: cd frontend && npm run dev

# Test flow:
# 1. Visit http://localhost:5173
# 2. Should redirect to /login
# 3. Click "Register" link
# 4. Create account
# 5. Should redirect to /ideas
```

---

## CHUNK 6: Frontend Ideas List & Voting

**Goal:** Display ideas and enable voting

### Files to Create:

1. **`/frontend/src/pages/IdeasPage.jsx`**
   - Fetch ideas on mount
   - Display loading state
   - Map over ideas and render IdeaCard components
   - Sort by score (highest first)
   - Show empty state if no ideas
   - "Submit New Idea" button (links to /submit)

2. **`/frontend/src/components/IdeaCard.jsx`**
   - Display idea title and descriptions
   - Show vote counts (score, upvotes, downvotes)
   - Render VoteButtons component
   - Expandable details (show full what/why/use_case)
   - Timestamp (created_at)

3. **`/frontend/src/components/VoteButtons.jsx`**
   - Upvote button (▲)
   - Downvote button (▼)
   - Highlight user's current vote
   - Call voteOnIdea() from API
   - Optimistic UI update (instant feedback)
   - Handle errors (revert on failure)

### Key Implementation Details:

- Use useEffect to fetch ideas
- Loading skeleton or spinner
- Optimistic updates for better UX
- Highlight user's vote with different color
- Refresh idea list after voting

### Testing After Chunk 6:
```bash
# With both servers running:
# 1. Login to the app
# 2. Should see list of ideas (if any exist)
# 3. Click upvote/downvote buttons
# 4. Should see vote counts update immediately
# 5. Refresh page - votes should persist
```

---

## CHUNK 7: Frontend Submit Idea Page (AI Flow)

**Goal:** Build AI-powered idea submission flow

### Files to Create:

1. **`/frontend/src/pages/SubmitIdeaPage.jsx`**
   - **Step 1: Freeform Input**
     - Large textarea for user to type freely
     - Character count (optional)
     - "Structure with AI" button
     - Loading state while AI processes

   - **Step 2: AI-Structured Output**
     - Show AI-generated fields (what, why, use_case)
     - Editable text inputs for each field
     - Title field (required)
     - "Submit Idea" button
     - "Start Over" button

   - State management:
     - Track current step (input vs. structured)
     - Store original text
     - Store AI-structured version
     - Track user edits

2. **`/frontend/src/components/Navigation.jsx`**
   - App header/navbar
   - Logo/app name
   - Navigation links:
     - "Browse Ideas" → /ideas
     - "Submit Idea" → /submit
   - User menu:
     - Show username
     - "Logout" button
   - Responsive (mobile-friendly)

### Key Implementation Details:

- Multi-step form (useState for step tracking)
- Show/hide sections based on current step
- Debounce "Structure with AI" button (prevent double-clicks)
- Store submission in state before final submit
- Clear form after successful submission
- Redirect to /ideas after submit

### Testing After Chunk 7:
```bash
# Complete user journey:
# 1. Login
# 2. Click "Submit Idea" in nav
# 3. Type: "We need a way for users to export their data to CSV"
# 4. Click "Structure with AI"
# 5. Wait for AI to process (should take 2-5 seconds)
# 6. Review AI-structured fields
# 7. Edit if needed
# 8. Click "Submit Idea"
# 9. Should redirect to /ideas
# 10. Should see new idea in list
# 11. Vote on the idea to test voting
```

---

## CHUNK 8: Final Integration & Testing

**Goal:** Polish the MVP and ensure everything works

### Tasks:

1. **Error Handling & Loading States**
   - Add error boundaries
   - Toast notifications for errors
   - Loading spinners throughout
   - Graceful API error handling
   - Empty states (no ideas yet, etc.)

2. **Styling Improvements**
   - Consistent spacing (Tailwind)
   - Color scheme (primary, secondary, danger)
   - Hover states on buttons
   - Focus states for accessibility
   - Responsive design (mobile, tablet, desktop)
   - Card shadows and borders

3. **Complete User Journey Testing**
   - [ ] Register new account
   - [ ] Login with existing account
   - [ ] Logout and login again
   - [ ] Submit idea with AI structuring
   - [ ] Edit AI-structured fields before submitting
   - [ ] View ideas list sorted by score
   - [ ] Upvote an idea
   - [ ] Downvote an idea
   - [ ] Change vote from up to down
   - [ ] Test with multiple users (different browsers)
   - [ ] Test invalid inputs (empty fields, etc.)

4. **Bug Fixes**
   - Fix any console errors
   - Fix any visual glitches
   - Handle edge cases (empty state, errors, etc.)
   - Test on different browsers

5. **Documentation**
   - Update main README.md with:
     - Project description
     - Setup instructions
     - Running the app
     - Environment variables needed
     - Tech stack
   - Add screenshots (optional)
   - Document API endpoints (optional)

6. **Git Commit & Push**
   ```bash
   git add -A
   git commit -m "Add complete MVP: backend APIs and React frontend

   Features:
   - User authentication (login/register)
   - AI-powered idea submission (Claude API)
   - Ideas browsing with vote counts
   - Upvote/downvote functionality
   - Protected routes and navigation
   - Complete frontend with TailwindCSS

   Backend:
   - Ideas, Votes, Submissions models and APIs
   - LLM service for text structuring
   - One-vote-per-user constraint
   - Vote count aggregation

   Frontend:
   - React + Vite + TailwindCSS
   - Auth context and protected routes
   - Ideas list page with voting
   - Submit idea page with AI structuring
   - Navigation header with logout

   🤖 Generated with Claude Code
   Co-Authored-By: Claude <noreply@anthropic.com>"

   git push origin main
   ```

### Final Checks:

- [ ] Backend server starts without errors
- [ ] Frontend builds without errors
- [ ] Database migrations work
- [ ] All environment variables documented
- [ ] README has setup instructions
- [ ] Main user flows tested end-to-end
- [ ] Code committed to Git
- [ ] Deployed (optional: Vercel for frontend, Railway for backend)

---

## Environment Variables Reference

### Backend (`/backend/.env`):
```env
# Application
APP_NAME=Feature Voting System
DEBUG=true

# Database
DATABASE_URL=sqlite:///./feature_voting.db

# Security
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# CORS
ALLOWED_ORIGINS=["http://localhost:3000","http://localhost:5173"]

# Admin User
ADMIN_EMAIL=admin@example.com
ADMIN_USERNAME=admin
ADMIN_PASSWORD=change-this-secure-password
ADMIN_FULL_NAME=System Administrator

# AI/LLM
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

### Frontend (`/frontend/.env`):
```env
VITE_API_URL=http://localhost:8000
```

---

## Running the Complete Application

### First Time Setup:

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
# Add your ANTHROPIC_API_KEY to .env

# Frontend
cd ../frontend
npm install
```

### Daily Development:

```bash
# Terminal 1 - Backend
cd backend
source venv/bin/activate
uvicorn app.main:app --reload

# Terminal 2 - Frontend
cd frontend
npm run dev
```

### Access:
- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

---

## Troubleshooting

### Common Issues:

1. **"Module not found" errors**
   - Backend: Make sure venv is activated
   - Frontend: Run `npm install`

2. **CORS errors in browser**
   - Check ALLOWED_ORIGINS in backend/.env
   - Should include http://localhost:5173

3. **"Unauthorized" errors**
   - Token may be expired (30 min default)
   - Logout and login again

4. **Claude API errors**
   - Verify ANTHROPIC_API_KEY in .env
   - Check API key is valid at console.anthropic.com
   - Check API rate limits

5. **Database errors**
   - Delete feature_voting.db and restart backend
   - Database will be recreated automatically

6. **Port already in use**
   - Backend: Change port with `--port 8001`
   - Frontend: Vite will prompt for different port

---

## Next Steps After MVP

### Phase 2 Features (Future):
- [ ] Similarity detection (show similar ideas before submitting)
- [ ] Admin dashboard (view idea sources, manage users)
- [ ] Competitor feature extraction (web scraping)
- [ ] Categories and tags
- [ ] Search and filtering
- [ ] User profiles and submission history
- [ ] Email notifications
- [ ] Export functionality

### Technical Improvements:
- [ ] Switch to PostgreSQL with pgvector
- [ ] Add Redis caching
- [ ] Implement proper logging
- [ ] Add comprehensive tests
- [ ] CI/CD pipeline
- [ ] Docker deployment
- [ ] Production environment setup

---

## Getting Help

If you encounter issues during implementation:

1. Check the console for error messages
2. Review the API documentation at /docs
3. Test API endpoints with curl or Postman
4. Check that all environment variables are set
5. Verify database is accessible
6. Ask Claude Code for help with specific errors

---

**🎯 Current Status**: Ready to implement Chunk 1

**📝 Next Action**: Say "start chunk 1" to begin implementation
