# Feature Voting System - MVP

A competitive intelligence and feature ideation system that enables users to submit feature ideas, vote on them, and uses AI to structure natural language submissions.

## MVP Features (Current Implementation)

### Backend (FastAPI + SQLite)
- ✅ User authentication (JWT tokens)
- ✅ Ideas management (create, list, view)
- ✅ Voting system (upvote/downvote, one vote per user)
- ✅ Manual idea submission with AI structuring (Claude API)
- ✅ Submissions tracking
- ✅ Vote count aggregation

### Frontend (React + Vite + TailwindCSS)
- ✅ User authentication (Login/Register)
- ✅ Protected routes
- ✅ Ideas list page with voting
- ✅ Submit idea page with AI-powered structuring
- ✅ Responsive design
- ✅ Navigation header

## Tech Stack

### Backend
- **Framework:** FastAPI
- **Database:** SQLite (SQLAlchemy ORM)
- **Authentication:** JWT tokens
- **AI/LLM:** Anthropic Claude API
- **Python Version:** 3.12+

### Frontend
- **Framework:** React 19
- **Build Tool:** Vite
- **Styling:** TailwindCSS v4
- **Routing:** React Router v7
- **HTTP Client:** Axios

## Project Structure

```
feature-voting-system/
├── backend/                 # FastAPI backend
│   ├── app/
│   │   ├── api/            # API endpoints
│   │   │   ├── ideas.py    # Ideas CRUD
│   │   │   ├── votes.py    # Voting endpoints
│   │   │   └── submissions.py  # AI submission flow
│   │   ├── models/         # SQLAlchemy models
│   │   ├── schemas/        # Pydantic schemas
│   │   ├── services/       # Business logic
│   │   │   └── llm_service.py  # Claude API integration
│   │   ├── database.py     # Database setup
│   │   ├── config.py       # Configuration
│   │   └── main.py         # FastAPI app entry
│   ├── requirements.txt
│   └── .env
├── frontend/               # React frontend
│   ├── src/
│   │   ├── components/    # Reusable components
│   │   │   ├── IdeaCard.jsx
│   │   │   ├── VoteButtons.jsx
│   │   │   └── ProtectedRoute.jsx
│   │   ├── pages/         # Page components
│   │   │   ├── LoginPage.jsx
│   │   │   ├── RegisterPage.jsx
│   │   │   ├── IdeasPage.jsx
│   │   │   └── SubmitIdeaPage.jsx
│   │   ├── contexts/      # React contexts
│   │   │   └── AuthContext.jsx
│   │   ├── services/      # API client
│   │   │   └── api.js
│   │   └── App.jsx
│   ├── package.json
│   └── .env
└── docs/                  # Documentation
```

## Quick Start

### Automated Setup (Recommended)

Use the provided scripts for easy setup and testing:

```bash
# 1. Full setup and testing (first time or after updates)
./setup_and_test.sh

# 2. Edit backend/.env to add your ANTHROPIC_API_KEY
nano backend/.env

# 3. Verify everything is ready
./verify.sh

# 4. Start both servers
./start.sh
```

**Script Documentation:** See [SCRIPTS.md](./SCRIPTS.md) for complete automation script reference

### Manual Setup

If you prefer manual setup, follow the instructions below.

## Setup Instructions

### Prerequisites
- Python 3.12 or higher
- Node.js 18+ and npm
- Anthropic API key (for AI structuring)

### Backend Setup

1. **Navigate to backend directory:**
   ```bash
   cd backend
   ```

2. **Create virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables:**

   Create a `.env` file in the `backend/` directory:
   ```env
   # Application
   APP_NAME=Feature Voting System
   DEBUG=true

   # Database
   DATABASE_URL=sqlite:///./feature_voting.db

   # Security
   SECRET_KEY=your-secret-key-change-in-production
   ALGORITHM=HS256
   ACCESS_TOKEN_EXPIRE_MINUTES=30

   # CORS
   ALLOWED_ORIGINS=["http://localhost:3000","http://localhost:5173"]

   # Admin User (created automatically)
   ADMIN_EMAIL=admin@example.com
   ADMIN_USERNAME=admin
   ADMIN_PASSWORD=admin123
   ADMIN_FULL_NAME=System Administrator

   # AI/LLM
   ANTHROPIC_API_KEY=sk-ant-your-key-here
   ```

5. **Start the backend server:**
   ```bash
   uvicorn app.main:app --reload
   ```

   Backend will run at: `http://localhost:8000`
   API docs available at: `http://localhost:8000/docs`

### Frontend Setup

1. **Navigate to frontend directory:**
   ```bash
   cd frontend
   ```

2. **Install dependencies:**
   ```bash
   npm install
   ```

3. **Configure environment variables:**

   Create a `.env` file in the `frontend/` directory:
   ```env
   VITE_API_URL=http://localhost:8000
   ```

4. **Start the frontend dev server:**
   ```bash
   npm run dev
   ```

   Frontend will run at: `http://localhost:5173`

## Running the Application

### Development Mode

You'll need two terminal windows:

**Terminal 1 - Backend:**
```bash
cd backend
source venv/bin/activate  # On Windows: venv\Scripts\activate
uvicorn app.main:app --reload
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev
```

Then open your browser to: `http://localhost:5173`

### First Time Use

1. **Register a new account** at `/register`
2. **Login** with your credentials
3. **Browse ideas** on the main page
4. **Submit a new idea** using the AI-powered submission flow
5. **Vote** on ideas (upvote/downvote)

### Default Admin Account

The system creates a default admin account on first run:
- **Username:** `admin`
- **Password:** `admin123`

**⚠️ Change this password in production!**

## API Endpoints

### Authentication
- `POST /auth/register` - Register new user
- `POST /auth/login` - Login (returns JWT token)
- `GET /auth/me` - Get current user

### Ideas
- `GET /ideas` - List all ideas (sorted by score)
- `GET /ideas/{id}` - Get single idea
- `POST /ideas` - Create idea (protected)

### Votes
- `POST /ideas/{id}/vote` - Vote on idea (protected)
  - Body: `{"vote_value": 1}` for upvote or `{"vote_value": -1}` for downvote

### Submissions
- `POST /submissions/structure` - Structure freeform text with AI (protected)
  - Body: `{"freeform_text": "Your idea..."}`
- `POST /submissions/submit` - Submit structured idea (protected)

## Development

### Testing

**Quick Tests:**
```bash
# Backend - Schema validation (no dependencies)
cd backend && source venv/bin/activate && python test_schemas.py

# Backend - Full API tests (requires running server)
cd backend && source venv/bin/activate && python test_api.py

# Frontend - Lint
cd frontend && npm run lint

# Frontend - Build validation
cd frontend && npm run build
```

**Documentation:**
- **[TESTING_GUIDE.md](./TESTING_GUIDE.md)** - Complete testing documentation
- **[TESTING_SUMMARY.md](./TESTING_SUMMARY.md)** - Quick reference

**Available Backend Tests:**
- `test_schemas.py` - Schema validation (fast, no dependencies)
- `test_api.py` - Authentication endpoints only
- `test_complete_api.py` - **ALL endpoints** (auth, ideas, votes, submissions) ⭐ **RECOMMENDED**
- `test_llm_service.py` - Claude API integration
- `test_chunk2_api.sh` - Ideas & voting flow (bash)
- `test_chunk3_api.sh` - Submissions flow (bash)

**Frontend Testing:**
- Linting with ESLint
- Build validation
- Manual browser testing (no automated tests yet)

### Building for Production

**Backend:**
```bash
# Backend runs with uvicorn, no build step needed
# For production, use gunicorn with uvicorn workers
```

**Frontend:**
```bash
cd frontend
npm run build
# Output in frontend/dist/
```

## Environment Variables

### Backend (.env)
- `DATABASE_URL` - SQLite database path
- `SECRET_KEY` - JWT signing key
- `ANTHROPIC_API_KEY` - Claude API key for AI structuring
- `ALLOWED_ORIGINS` - CORS allowed origins (JSON array)
- `ADMIN_*` - Default admin user credentials

### Frontend (.env)
- `VITE_API_URL` - Backend API base URL

## Troubleshooting

### Common Issues

1. **"Module not found" errors**
   - Backend: Make sure virtual environment is activated
   - Frontend: Run `npm install`

2. **CORS errors in browser**
   - Check `ALLOWED_ORIGINS` in backend `.env`
   - Should include `http://localhost:5173`

3. **"Unauthorized" errors**
   - Token may be expired (default 30 minutes)
   - Logout and login again

4. **Claude API errors**
   - Verify `ANTHROPIC_API_KEY` in backend `.env`
   - Check API key validity at console.anthropic.com
   - Check API rate limits

5. **Database errors**
   - Delete `feature_voting.db` and restart backend
   - Database will be recreated automatically

## Documentation

- [REQUIREMENTS.md](./docs/REQUIREMENTS.md) - Full system requirements
- [DATABASE_SCHEMA.sql](./docs/DATABASE_SCHEMA.sql) - Complete database schema
- [MVP_IMPLEMENTATION_GUIDE.md](./MVP_IMPLEMENTATION_GUIDE.md) - Implementation guide
- [BACKEND_SUMMARY.md](./BACKEND_SUMMARY.md) - Backend implementation details

## Future Enhancements

### Phase 2 Features (Not Yet Implemented)
- [ ] Similarity detection (show similar ideas before submitting)
- [ ] Admin dashboard (view idea sources, manage users)
- [ ] Competitor feature extraction (web scraping)
- [ ] Categories and tags
- [ ] Search and filtering
- [ ] User profiles and submission history
- [ ] Email notifications
- [ ] PostgreSQL with pgvector for embeddings

### Technical Improvements
- [ ] Comprehensive test suite
- [ ] CI/CD pipeline
- [ ] Docker deployment
- [ ] Production environment configuration
- [ ] Logging and monitoring
- [ ] Rate limiting
- [ ] Caching (Redis)

## License

See [LICENSE](./LICENSE) file.

## Contributing

This is an MVP implementation. For the full system architecture and future roadmap, see the documentation in the `docs/` directory.

---

**🤖 Generated with [Claude Code](https://claude.com/claude-code)**

**Co-Authored-By: Claude <noreply@anthropic.com>**
