# Getting Started - Feature Voting System

## For Claude Code: Building This Project

This guide is designed to help Claude Code (or any AI coding assistant) understand how to build this project from scratch.

## Project Context

This is a **competitive intelligence and feature ideation system** that:
1. Extracts features from competitor products
2. Converts them to anonymized ideas
3. Allows manual idea submission with AI assistance
4. Uses semantic similarity to prevent duplicates
5. Enables voting to prioritize features

See [ARCHITECTURE.md](./ARCHITECTURE.md) for complete system design and [REQUIREMENTS.md](./REQUIREMENTS.md) for detailed specifications.

## Technology Stack Summary

- **Backend**: FastAPI (Python 3.11+), PostgreSQL 16 + pgvector, Redis
- **Frontend**: React 18+, Vite, TailwindCSS
- **AI**: Claude API (Anthropic), OpenAI embeddings
- **Infrastructure**: Docker Compose for local dev

## Initial Project Setup

### Phase 1: Project Structure

Create the following directory structure:

```
feature-voting-system/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                    # FastAPI app entry
│   │   ├── config.py                  # Settings/config
│   │   ├── database.py                # DB connection
│   │   ├── models/                    # SQLAlchemy models
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── competitor.py
│   │   │   ├── product.py
│   │   │   ├── feature.py
│   │   │   ├── idea.py
│   │   │   ├── vote.py
│   │   │   ├── submission.py
│   │   │   └── draft.py
│   │   ├── schemas/                   # Pydantic schemas
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── idea.py
│   │   │   ├── vote.py
│   │   │   └── auth.py
│   │   ├── api/                       # API routes
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   ├── ideas.py
│   │   │   ├── votes.py
│   │   │   ├── submissions.py
│   │   │   ├── competitors.py
│   │   │   └── admin.py
│   │   ├── services/                  # Business logic
│   │   │   ├── __init__.py
│   │   │   ├── auth_service.py
│   │   │   ├── llm_service.py         # Claude API
│   │   │   ├── similarity_service.py  # Vector search
│   │   │   ├── idea_service.py
│   │   │   └── voting_service.py
│   │   └── utils/
│   │       ├── __init__.py
│   │       ├── security.py            # Password hashing, JWT
│   │       └── dependencies.py        # FastAPI deps
│   ├── alembic/                       # DB migrations
│   ├── tests/
│   ├── requirements.txt
│   ├── .env.example
│   └── README.md
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── auth/
│   │   │   ├── ideas/
│   │   │   ├── submission/
│   │   │   └── common/
│   │   ├── pages/
│   │   ├── hooks/
│   │   ├── services/
│   │   ├── context/
│   │   ├── App.jsx
│   │   └── main.jsx
│   ├── public/
│   ├── package.json
│   ├── vite.config.js
│   └── tailwind.config.js
├── docs/                              # Documentation
│   ├── ARCHITECTURE.md
│   ├── DATABASE_SCHEMA.sql
│   ├── REQUIREMENTS.md
│   └── GETTING_STARTED.md (this file)
├── docker-compose.yml
├── .gitignore
└── README.md
```

### Phase 2: Configuration Files

#### docker-compose.yml
```yaml
version: '3.8'

services:
  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: featurevote
      POSTGRES_PASSWORD: devpassword
      POSTGRES_DB: featurevote_db
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U featurevote"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
```

#### backend/requirements.txt
```
fastapi==0.109.0
uvicorn[standard]==0.27.0
sqlalchemy==2.0.25
alembic==1.13.1
psycopg2-binary==2.9.9
pgvector==0.2.4
pydantic==2.5.3
pydantic-settings==2.1.0
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.6
anthropic==0.8.1
openai==1.10.0
beautifulsoup4==4.12.3
requests==2.31.0
pytest==7.4.4
pytest-asyncio==0.23.3
httpx==0.26.0
```

#### frontend/package.json
```json
{
  "name": "feature-voting-frontend",
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview",
    "lint": "eslint . --ext js,jsx",
    "test": "vitest"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.21.0",
    "axios": "^1.6.5",
    "zustand": "^4.4.7"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.2.1",
    "vite": "^5.0.11",
    "tailwindcss": "^3.4.1",
    "autoprefixer": "^10.4.16",
    "postcss": "^8.4.33",
    "eslint": "^8.56.0",
    "eslint-plugin-react": "^7.33.2",
    "vitest": "^1.2.0"
  }
}
```

#### backend/.env.example
```env
# Database
DATABASE_URL=postgresql://featurevote:devpassword@localhost:5432/featurevote_db
REDIS_URL=redis://localhost:6379/0

# API Keys
ANTHROPIC_API_KEY=your_claude_api_key_here
OPENAI_API_KEY=your_openai_api_key_here

# Security
SECRET_KEY=your-secret-key-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Application
ENVIRONMENT=development
DEBUG=true
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000

# Similarity Settings
SIMILARITY_THRESHOLD=0.7
MAX_SIMILAR_RESULTS=5

# LLM Settings
LLM_MODEL=claude-sonnet-4-5-20250929
LLM_TEMPERATURE=0.7
MAX_TOKENS=2000
```

### Phase 3: Database Setup

1. **Start Docker services:**
```bash
docker-compose up -d
```

2. **Create database schema:**
```bash
# Copy DATABASE_SCHEMA.sql from docs/ to backend/
# Then run:
psql -h localhost -U featurevote -d featurevote_db -f backend/DATABASE_SCHEMA.sql
```

3. **Setup Alembic for migrations:**
```bash
cd backend
alembic init alembic
# Configure alembic.ini and alembic/env.py
```

### Phase 4: Backend Implementation Priority

Build in this order:

#### 4.1 Core Setup (Day 1)
- [ ] `backend/app/config.py` - Settings management
- [ ] `backend/app/database.py` - SQLAlchemy setup
- [ ] `backend/app/main.py` - FastAPI app with CORS

#### 4.2 Authentication (Day 1-2)
- [ ] `backend/app/models/user.py` - User model
- [ ] `backend/app/schemas/user.py` - User schemas
- [ ] `backend/app/schemas/auth.py` - Auth schemas
- [ ] `backend/app/utils/security.py` - Password hashing, JWT
- [ ] `backend/app/services/auth_service.py` - Auth logic
- [ ] `backend/app/api/auth.py` - Login/register endpoints
- [ ] `backend/app/utils/dependencies.py` - Auth dependencies

#### 4.3 Ideas & Voting (Day 2-3)
- [ ] `backend/app/models/idea.py` - Idea model with vector field
- [ ] `backend/app/models/vote.py` - Vote model
- [ ] `backend/app/schemas/idea.py` - Idea schemas
- [ ] `backend/app/schemas/vote.py` - Vote schemas
- [ ] `backend/app/services/idea_service.py` - CRUD operations
- [ ] `backend/app/services/voting_service.py` - Vote logic
- [ ] `backend/app/api/ideas.py` - Idea endpoints
- [ ] `backend/app/api/votes.py` - Voting endpoints

#### 4.4 Manual Submission with AI (Day 3-4)
- [ ] `backend/app/models/submission.py` - Submission tracking
- [ ] `backend/app/models/draft.py` - Draft storage
- [ ] `backend/app/services/llm_service.py` - Claude API integration
- [ ] `backend/app/services/similarity_service.py` - Vector search
- [ ] `backend/app/api/submissions.py` - Submission endpoints

#### 4.5 Competitor Intelligence (Day 5-6)
- [ ] `backend/app/models/competitor.py` - Competitor model
- [ ] `backend/app/models/product.py` - Product model
- [ ] `backend/app/models/feature.py` - Feature model
- [ ] `backend/app/services/scraping_service.py` - Web scraping
- [ ] `backend/app/api/competitors.py` - Competitor endpoints
- [ ] Background task setup with Celery

#### 4.6 Admin Features (Day 6-7)
- [ ] `backend/app/api/admin.py` - Admin endpoints
- [ ] Analytics queries
- [ ] Source attribution views
- [ ] User management

### Phase 5: Frontend Implementation Priority

#### 5.1 Setup & Auth (Day 1-2)
- [ ] Vite + React + TailwindCSS setup
- [ ] Axios configuration
- [ ] Auth context
- [ ] Login/Register components
- [ ] Protected route wrapper

#### 5.2 Idea Browsing & Voting (Day 2-3)
- [ ] Idea list component
- [ ] Idea card component
- [ ] Vote button component
- [ ] Filters and sorting
- [ ] Pagination

#### 5.3 Manual Submission Flow (Day 3-5)
- [ ] Freeform text area with auto-save
- [ ] Real-time similarity panel
- [ ] Decision interface (vote vs submit)
- [ ] AI structuring editor
- [ ] Submission confirmation

#### 5.4 Admin Dashboard (Day 5-6)
- [ ] Competitor management UI
- [ ] Product review interface
- [ ] Source attribution view
- [ ] Analytics dashboard
- [ ] User management

### Phase 6: Testing & Refinement

- [ ] Backend unit tests (pytest)
- [ ] API integration tests
- [ ] Frontend component tests
- [ ] End-to-end testing
- [ ] Performance optimization
- [ ] Security review

## Development Workflow

### Starting Development
```bash
# 1. Start infrastructure
docker-compose up -d

# 2. Start backend (in one terminal)
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 3. Start frontend (in another terminal)
cd frontend
npm install
npm run dev
```

### Access Points
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- PostgreSQL: localhost:5432
- Redis: localhost:6379

### Environment Variables
Copy `.env.example` to `.env` and fill in:
- `ANTHROPIC_API_KEY` - Get from https://console.anthropic.com/
- `OPENAI_API_KEY` - Get from https://platform.openai.com/ (for embeddings)
- `SECRET_KEY` - Generate with: `python -c "import secrets; print(secrets.token_urlsafe(32))"`

## Key Implementation Notes

### Vector Embeddings
- Use OpenAI `text-embedding-ada-002` (1536 dimensions) OR Claude embeddings
- Generate on idea creation and cache
- Store in PostgreSQL vector column
- Use pgvector's HNSW index for fast similarity search

### LLM Integration
- Use Claude API for:
  - Product discovery from competitor websites
  - Feature extraction
  - Idea anonymization
  - Freeform text structuring
- Implement retry logic with exponential backoff
- Cache responses where appropriate
- Handle rate limiting gracefully

### Similarity Detection
- Debounce user input (2-3 second pause)
- Generate embedding of draft text
- Query pgvector with cosine similarity
- Return top 5 results above threshold (0.7)
- Display with similarity scores

### Web Scraping
- Respect robots.txt
- Add delays between requests (2-5 seconds)
- Use proper user agent identification
- Handle both static and JavaScript-rendered content
- Implement error handling and retries

## Testing Strategy

### Backend Tests
```bash
cd backend
pytest tests/ -v
pytest tests/test_similarity.py  # Specific test
pytest --cov=app tests/          # With coverage
```

### Frontend Tests
```bash
cd frontend
npm test
npm run test:coverage
```

## Common Issues & Solutions

### Issue: pgvector extension not found
```sql
-- Connect to database and run:
CREATE EXTENSION IF NOT EXISTS vector;
```

### Issue: CORS errors
Check `ALLOWED_ORIGINS` in `.env` includes your frontend URL

### Issue: JWT token expired
Tokens expire in 30 minutes by default. Implement token refresh or re-login.

### Issue: Similarity search is slow
- Ensure HNSW index is created
- Check if embeddings are being cached
- Consider reducing `MAX_SIMILAR_RESULTS`

### Issue: LLM API rate limiting
- Implement exponential backoff
- Add caching layer
- Reduce concurrent requests

## Deployment Checklist

- [ ] Change all default passwords
- [ ] Set strong `SECRET_KEY`
- [ ] Use production database
- [ ] Enable HTTPS
- [ ] Configure proper CORS origins
- [ ] Set up database backups
- [ ] Configure logging
- [ ] Set up monitoring
- [ ] Review security settings
- [ ] Test all critical flows

## Resources

- FastAPI docs: https://fastapi.tiangolo.com/
- React docs: https://react.dev/
- pgvector: https://github.com/pgvector/pgvector
- Anthropic Claude: https://docs.anthropic.com/
- OpenAI Embeddings: https://platform.openai.com/docs/guides/embeddings

## Questions for Claude Code

When implementing, consider:
1. Should we use OpenAI or Claude for embeddings? (Cost vs consistency)
2. Celery vs simple background threads for async tasks?
3. Session-based vs token-based auth for better UX?
4. Server-side vs client-side pagination for ideas list?
5. WebSockets vs polling for real-time vote updates?

## Next Steps

1. Review [ARCHITECTURE.md](./ARCHITECTURE.md) for system design
2. Review [DATABASE_SCHEMA.sql](./DATABASE_SCHEMA.sql) for data model
3. Review [REQUIREMENTS.md](./REQUIREMENTS.md) for detailed specs
4. Set up development environment (Docker, Python, Node.js)
5. Start with Phase 4.1: Core Setup
6. Build iteratively, testing as you go
7. Deploy to staging for user testing