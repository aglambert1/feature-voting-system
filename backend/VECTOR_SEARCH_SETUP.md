# Vector Search Setup Guide

## Overview

The semantic search feature uses sqlite-vec (development) or pgvector (production) for vector similarity search. Embeddings are generated via the Voyage AI API (`voyage-3.5-lite` model, 1024 dimensions).

## Requirements

### Voyage AI API Key

Embeddings are generated via the Voyage AI API. Get a key from https://dash.voyageai.com/ and set it in your `.env`:

```bash
VOYAGE_API_KEY=your-key-here
```

### Database: SQLite (Development) or PostgreSQL (Production)

The app automatically selects the right vector backend based on `DATABASE_URL`.

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
- All existing features
- Idea submission
- Voting
- Product management

**What doesn't work:**
- "Checking for similar ideas..." feature
- Duplicate detection during submission

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

3. **Set VOYAGE_API_KEY environment variable** in your hosting dashboard.

4. **The app will automatically:**
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

## Migrating Existing Ideas

After setting up vector search, backfill embeddings for existing ideas:

```bash
cd backend
python migrate_embeddings.py
```

This uses the Voyage AI API to generate 1024-dimensional embeddings for all existing ideas.

## Troubleshooting

### "no such module: vec0"

**Cause:** SQLite extension not loaded
**Solution:** Use Homebrew Python (Option 1 above)

### "Vector search will not be available"

**Cause:** Extension loading failed
**Impact:** App works but no similarity search
**Solution:** Use Homebrew Python or PostgreSQL

### Voyage AI API errors

**Cause:** Missing or invalid `VOYAGE_API_KEY`
**Solution:** Check your `.env` file or hosting environment variables. Get a key from https://dash.voyageai.com/

## Architecture

### Development (SQLite)
```
User Input
    ↓
Voyage AI API (voyage-3.5-lite)
    ↓
1024-dim embedding
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
Voyage AI API (voyage-3.5-lite)
    ↓
1024-dim embedding
    ↓
ideas.embedding column (pgvector)
    ↓
embedding <=> operator search
    ↓
Similar ideas
```

Both use the same `VectorService` abstraction layer - no code changes needed!
