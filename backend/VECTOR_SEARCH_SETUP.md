# Vector Search Setup Guide

## Overview

The semantic search feature uses sqlite-vec (development) or pgvector (production) for vector similarity search. This document explains setup requirements and troubleshooting.

## macOS Development Setup Issue

### Problem

Python.org's official Python builds for macOS have SQLite compiled **without** extension loading support for security reasons. This affects the `sqlite-vec` extension.

**Symptoms:**
- Error: `'sqlite3.Connection' object has no attribute 'enable_load_extension'`
- Error: `no such module: vec0`
- Warning: `Vector search will not be available`

### Solutions

#### Option 1: Use Homebrew Python (RECOMMENDED)

Homebrew's Python builds include SQLite with extension support enabled. Use the latest version available.

```bash
# Install Homebrew Python (if not already installed)
# This gets the latest version (currently Python 3.13)
brew install python

# Create virtual environment with Homebrew Python
/opt/homebrew/bin/python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Verify extension loading works
python -c "import sqlite3; conn = sqlite3.connect(':memory:'); conn.enable_load_extension(True); print('✓ Extension loading supported')"
```

#### Option 2: Run Without Vector Search (Development Only)

The app has graceful degradation built-in. It will work without vector search - users just won't see similarity suggestions.

**What works without vector search:**
- ✅ All existing features
- ✅ Idea submission
- ✅ Voting
- ✅ Product management

**What doesn't work:**
- ❌ "Checking for similar ideas..." feature
- ❌ Duplicate detection during submission

**To run:**
```bash
# Just start the backend normally
uvicorn app.main:app --reload
```

You'll see warnings at startup:
```
✗ Failed to load sqlite-vec: ...
(Vector search will not be available)
```

This is **expected** and the app will continue to work.

#### Option 3: Use PostgreSQL Locally

Install PostgreSQL with pgvector to test the full feature set.

```bash
# Install PostgreSQL
brew install postgresql@15

# Start PostgreSQL
brew services start postgresql@15

# Install pgvector
brew install pgvector

# Create database
createdb feature_voting

# Update .env file
DATABASE_URL=postgresql://localhost/feature_voting

# Install PostgreSQL Python driver
pip install psycopg2-binary

# Start backend
uvicorn app.main:app --reload
```

The app will automatically detect PostgreSQL and use pgvector instead of sqlite-vec.

## Production Deployment

### PostgreSQL with pgvector (REQUIRED)

Production deployments **must** use PostgreSQL with pgvector. SQLite is only for development.

**Setup:**

1. **Install pgvector extension:**
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```

2. **Set DATABASE_URL environment variable:**
   ```
   DATABASE_URL=postgresql://user:password@host:port/database
   ```

3. **The app will automatically:**
   - Detect PostgreSQL
   - Use pgvector instead of sqlite-vec
   - Create necessary indexes

**Performance optimization:**
```sql
-- Create HNSW index for faster similarity search
CREATE INDEX idx_ideas_embedding ON ideas
USING hnsw (embedding vector_cosine_ops);
```

## Testing Vector Search

### Test Extension Loading

```bash
python -c "
import sqlite_vec
import sqlite3

conn = sqlite3.connect(':memory:')
try:
    sqlite_vec.load(conn)
    print('✓ sqlite-vec loaded successfully')
    conn.execute('CREATE VIRTUAL TABLE test USING vec0(id INTEGER PRIMARY KEY, emb FLOAT[3])')
    print('✓ Virtual table created')
except Exception as e:
    print(f'✗ Error: {e}')
"
```

**Expected output with working setup:**
```
✓ sqlite-vec loaded successfully
✓ Virtual table created
```

**Expected output without extension support:**
```
✗ Error: 'sqlite3.Connection' object has no attribute 'load_extension'
```

### Test Backend Startup

```bash
# Start backend
uvicorn app.main:app --reload

# Check startup logs for:
# ✓ Loaded sqlite-vec extension
# ✓ Model loaded successfully (384 dimensions)
# ✓ sqlite-vec virtual table created
```

### Test Similarity Search API

```bash
# Create a test idea first, then:
curl -X GET "http://localhost:8000/ideas/similar?q=export%20data%20to%20CSV&product_id=1" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

Expected response if working:
```json
[
  {
    "id": 1,
    "title": "CSV Export Feature",
    "what_description": "Add ability to export data to CSV format",
    "similarity_score": 0.85
  }
]
```

Expected response if not working:
```json
{
  "detail": "Semantic search unavailable - embedding model not loaded"
}
```

## Migrating Existing Ideas

After setting up vector search, backfill embeddings for existing ideas:

```bash
cd backend
python migrate_embeddings.py
```

**Expected output:**
```
============================================================
Embedding Migration Script
============================================================

Loading SentenceTransformer model (all-MiniLM-L6-v2)...
✓ Model loaded successfully (384 dimensions)

Checking vec_ideas virtual table...
✓ vec_ideas table ready

Fetching active ideas from database...
✓ Found 42 active ideas to process

Generating and storing embeddings...

  Processed 10/42 ideas (10 successful, 0 errors)
  Processed 20/42 ideas (20 successful, 0 errors)
  Processed 30/42 ideas (30 successful, 0 errors)
  Processed 40/42 ideas (40 successful, 0 errors)

============================================================
✓ Migration complete!
  Total ideas: 42
  Successfully embedded: 42
  Errors: 0
  Success rate: 100.0%
============================================================
```

## Troubleshooting

### "no such module: vec0"

**Cause:** SQLite extension not loaded
**Solution:** Use Homebrew Python (Option 1 above)

### "Semantic search unavailable - embedding model not loaded"

**Cause:** SentenceTransformer model failed to load
**Solution:** Check startup logs for model loading errors. Ensure torch and sentence-transformers are installed.

### "Vector search will not be available"

**Cause:** Extension loading failed
**Impact:** App works but no similarity search
**Solution:** Use Homebrew Python or PostgreSQL

### Model loading is slow (2-3 seconds)

**Expected behavior:** First startup downloads the model (~80MB). Subsequent startups load from cache in ~2-3 seconds.

**To pre-download model:**
```bash
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
```

## Architecture

### Development (SQLite)
```
User Input
    ↓
SentenceTransformer (all-MiniLM-L6-v2)
    ↓
384-dim embedding
    ↓
vec_ideas virtual table (sqlite-vec)
    ↓
vec_distance_cosine() search
    ↓
Similar ideas
```

### Production (PostgreSQL)
```
User Input
    ↓
SentenceTransformer (all-MiniLM-L6-v2)
    ↓
384-dim embedding
    ↓
ideas.embedding column (pgvector)
    ↓
embedding <=> operator search
    ↓
Similar ideas
```

Both use the same `VectorService` abstraction layer - no code changes needed!
