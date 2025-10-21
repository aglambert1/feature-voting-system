# Feature Voting System - Architecture Documentation

## System Overview

A competitive intelligence and feature ideation system that discovers competitor products, extracts their features, and generates anonymized feature ideas for internal voting. Users can also manually submit ideas through natural language input with AI-assisted structuring and intelligent duplicate detection.

## Technology Stack

### Backend
- **Framework**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL 16 with pgvector extension
- **Caching**: Redis
- **ORM**: SQLAlchemy with Alembic migrations
- **Authentication**: JWT tokens
- **Task Queue**: Celery (for background jobs)
- **Testing**: pytest, pytest-asyncio

### Frontend
- **Framework**: React 18+
- **Build Tool**: Vite
- **Styling**: TailwindCSS
- **State Management**: React Context API / Zustand
- **HTTP Client**: Axios
- **Routing**: React Router v6
- **Testing**: Jest, React Testing Library

### AI/ML Integration
- **LLM**: Anthropic Claude API (primary)
- **Embeddings**: OpenAI embeddings API or Claude
- **Vector Search**: pgvector with HNSW indexing
- **Web Scraping**: BeautifulSoup4, Playwright (for JavaScript-rendered content)

### Infrastructure
- **Containerization**: Docker, Docker Compose
- **CI/CD**: GitHub Actions
- **Version Control**: Git, GitHub

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         Frontend (React)                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Idea Browsing│  │ Manual Submit│  │ Admin Panel  │      │
│  │   & Voting   │  │  with AI Help│  │              │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                            │ REST API (JSON)
┌─────────────────────────────────────────────────────────────┐
│                      Backend (FastAPI)                       │
│  ┌──────────────────────────────────────────────────────┐  │
│  │                    API Layer                          │  │
│  │  /auth  /ideas  /votes  /submissions  /competitors   │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │                  Service Layer                        │  │
│  │  • AuthService                                        │  │
│  │  • LLMService (Claude API integration)              │  │
│  │  • SimilarityService (vector search)                 │  │
│  │  • ScrapingService (competitor data collection)      │  │
│  │  • IdeaService                                        │  │
│  │  • VotingService                                      │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │                Background Tasks (Celery)              │  │
│  │  • Competitor product discovery                       │  │
│  │  • Feature extraction from websites                   │  │
│  │  • Embedding generation                               │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│                     Data Layer                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  PostgreSQL  │  │    Redis     │  │  Claude API  │      │
│  │  + pgvector  │  │  (Cache/Jobs)│  │  (LLM calls) │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. User Authentication & Authorization
- JWT-based authentication
- Role-based access control (Admin, Voter, Viewer)
- User registration and login
- Session management

### 2. Manual Idea Submission Flow
**User Experience:**
1. User enters freeform text in a single text area
2. System performs real-time similarity detection (debounced)
3. Similar existing ideas are shown with vote counts
4. User chooses: Vote on existing OR Continue with new idea
5. If continuing: AI structures the idea into What/Why/UseCase format
6. User can edit AI-generated structure
7. Final submission with source tracking

**Technical Implementation:**
- Frontend: React component with debounced input
- Backend: Similarity API endpoint with vector search
- LLM: Claude API for structuring freeform text
- Database: Store original text + structured version + user edits

### 3. Competitive Intelligence Engine
**Automated Workflow:**
1. Admin inputs competitor list
2. System scrapes competitor websites
3. LLM identifies products and features
4. Admin confirms products to include
5. System extracts features and converts to anonymized ideas
6. Ideas stored with competitor attribution (admin-only visibility)

**Technical Implementation:**
- Web scraping with rate limiting
- LLM-based feature identification
- Anonymization engine (removes competitor-specific terms)
- Background job processing (Celery)

### 4. Similarity Detection Engine
**Features:**
- Real-time semantic similarity search
- Vector embeddings using OpenAI/Claude
- pgvector for efficient nearest-neighbor search
- Configurable similarity threshold (default: 0.7)
- Returns top 5 similar ideas with scores

**Technical Implementation:**
- Generate embeddings on idea submission
- Store in PostgreSQL vector column
- HNSW index for fast retrieval
- Cosine similarity scoring

### 5. Voting System
- Upvote/downvote mechanism
- One vote per user per idea
- Vote history tracking
- Real-time vote count updates
- Leaderboard/ranking views

### 6. Admin Dashboard
**Features:**
- Competitor management
- Product confirmation workflow
- View idea sources (competitor or submitter)
- User management
- Analytics and reporting
- Merge duplicate ideas

## Data Flow Examples

### Example 1: Manual Idea Submission
```
User types text
    ↓
Frontend debounces (2-3 sec)
    ↓
POST /api/similarity/search
    ↓
Backend generates embedding
    ↓
PostgreSQL vector search
    ↓
Return similar ideas
    ↓
User decides to continue
    ↓
POST /api/ideas/structure
    ↓
Claude API structures text
    ↓
Return What/Why/UseCase
    ↓
User edits and submits
    ↓
POST /api/ideas
    ↓
Store in database with tracking
```

### Example 2: Competitor Feature Extraction
```
Admin adds competitor
    ↓
Background job triggered
    ↓
Scrape competitor website
    ↓
Extract text content
    ↓
Claude API: identify products
    ↓
Admin confirms products
    ↓
For each product:
    ↓
Claude API: extract features
    ↓
Claude API: anonymize features
    ↓
Generate embeddings
    ↓
Store as ideas with source tracking
```

## Security Considerations

### Authentication & Authorization
- JWT tokens with short expiration (30 min)
- Refresh token mechanism
- Password hashing with bcrypt
- Role-based access control at API level

### Data Privacy
- Idea submitter identity visible only to admins
- Competitor source visible only to admins
- Public voting interface shows only anonymized ideas
- Audit logging for all sensitive operations

### API Security
- Rate limiting on all endpoints
- Input validation and sanitization
- SQL injection prevention (parameterized queries)
- XSS prevention (output encoding)
- CORS configuration
- API key rotation for external services

### Compliance
- Only scrape publicly accessible data
- Respect robots.txt
- Rate limit web requests
- Clear terms for user-generated content

## Performance Optimization

### Database
- Indexes on frequently queried columns
- Materialized view for vote counts
- Connection pooling
- Query optimization

### Caching Strategy
- Redis cache for:
  - User sessions
  - Frequently accessed ideas
  - Vote counts
  - LLM responses (when appropriate)
- Cache invalidation on updates

### API Performance
- Async/await for I/O operations
- Background jobs for long-running tasks
- Pagination for list endpoints
- Lazy loading on frontend

### Vector Search
- HNSW index for fast similarity search
- Pre-computed embeddings
- Batch embedding generation
- Progressive similarity updates

## Scalability Considerations

### Current Architecture (MVP)
- Single backend server
- Single database instance
- Suitable for: 1-100 concurrent users, 10k ideas

### Future Scaling Options
- Horizontal backend scaling (load balancer)
- Database replication (read replicas)
- Separate Celery workers
- CDN for frontend static assets
- Microservices split (if needed)

## Deployment Architecture

### Development Environment
```
Docker Compose:
- PostgreSQL + pgvector
- Redis
- Backend (hot reload)
- Frontend (Vite dev server)
```

### Production Environment
```
- Frontend: Static hosting (Vercel, Netlify, S3+CloudFront)
- Backend: Container hosting (Railway, Render, AWS ECS)
- Database: Managed PostgreSQL (AWS RDS, Supabase)
- Redis: Managed Redis (AWS ElastiCache, Redis Cloud)
- Background Jobs: Separate container instances
```

## Monitoring & Observability

### Logging
- Structured logging (JSON format)
- Log levels: DEBUG, INFO, WARNING, ERROR
- Request/response logging
- Error tracking with stack traces

### Metrics (Future)
- API response times
- Database query performance
- LLM API latency and costs
- User engagement metrics
- System resource usage

### Health Checks
- `/health` endpoint for service status
- Database connectivity check
- Redis connectivity check
- External API status

## Development Workflow

### Local Development
1. Clone repository
2. Run `docker-compose up` (starts all services)
3. Backend: `cd backend && uvicorn app.main:app --reload`
4. Frontend: `cd frontend && npm run dev`
5. Access at `http://localhost:5173`

### Testing
- Unit tests for services and utilities
- Integration tests for API endpoints
- End-to-end tests for critical flows
- Test coverage target: 80%+

### Git Workflow
- Main branch: production-ready code
- Feature branches: `feature/description`
- Bug fixes: `fix/description`
- Commit messages: descriptive and clear
- GitHub Actions: automated testing on push

## API Design Principles

### RESTful Design
- Resource-based URLs
- HTTP methods: GET, POST, PUT, PATCH, DELETE
- Consistent response format
- Proper status codes

### Response Format
```json
{
  "success": true,
  "data": { ... },
  "message": "Optional message",
  "error": null
}
```

### Error Handling
```json
{
  "success": false,
  "data": null,
  "message": "Error description",
  "error": {
    "code": "ERROR_CODE",
    "details": { ... }
  }
}
```

## Future Enhancements

### Phase 2
- Advanced analytics dashboard
- Idea trend analysis
- Gap analysis (compare to roadmap)
- Email notifications
- Export functionality

### Phase 3
- Machine learning for better similarity
- Automated idea merging
- Multi-language support
- Mobile app (React Native)
- API for integrations (Jira, Slack)

## References

- [Database Schema](./DATABASE_SCHEMA.sql)
- [Requirements Documentation](./REQUIREMENTS.md)
- [API Documentation](./API.md) (to be created)
- [Deployment Guide](./DEPLOYMENT.md) (to be created)