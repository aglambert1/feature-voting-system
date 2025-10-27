# Feature Voting System - Backend

A simple FastAPI backend with user authentication to get you started with web development!

## What You've Built

This is a basic REST API with:
- User registration and login
- JWT token authentication
- SQLite database (easy for learning)
- Comprehensive code comments explaining everything

## Project Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # Main FastAPI application
│   ├── config.py            # Settings and configuration
│   ├── database.py          # Database connection
│   ├── models/
│   │   ├── __init__.py
│   │   └── user.py          # User database model
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── auth.py          # Request/response schemas
│   ├── api/
│   │   ├── __init__.py
│   │   └── auth.py          # Authentication routes
│   └── utils/
│       ├── __init__.py
│       └── security.py      # Password hashing, JWT tokens
├── requirements.txt         # Python dependencies
├── .env.example            # Example environment variables
└── README.md               # This file
```

## Getting Started

### 1. Set Up Python Environment

```bash
# Navigate to the backend directory
cd backend

# Create a virtual environment (keeps packages isolated)
python -m venv venv

# Activate the virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables

```bash
# Copy the example env file
cp .env.example .env

# Edit .env and set a secure SECRET_KEY
# Generate one with: python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 3. Run the Server

```bash
# Start the development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# The --reload flag automatically restarts the server when you change code
```

### 4. Test It Out!

Open your browser and visit:
- **API Documentation**: http://localhost:8000/docs (interactive Swagger UI)
- **Alternative Docs**: http://localhost:8000/redoc (ReDoc format)
- **Health Check**: http://localhost:8000/health

## How to Use the API

### Option 1: Interactive Documentation (Easiest!)

1. Go to http://localhost:8000/docs
2. Click on any endpoint to expand it
3. Click "Try it out"
4. Fill in the required fields
5. Click "Execute"

### Option 2: Using curl (Command Line)

```bash
# 1. Register a new user
curl -X POST "http://localhost:8000/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "username": "testuser",
    "password": "password123",
    "full_name": "Test User"
  }'

# 2. Login to get an access token
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=testuser&password=password123"

# You'll get a response like:
# {"access_token":"eyJhbGc...", "token_type":"bearer"}

# 3. Use the token to access protected routes
curl -X GET "http://localhost:8000/auth/me" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

### Option 3: Using Python requests

```python
import requests

# Base URL
BASE_URL = "http://localhost:8000"

# 1. Register
response = requests.post(
    f"{BASE_URL}/auth/register",
    json={
        "email": "test@example.com",
        "username": "testuser",
        "password": "password123",
        "full_name": "Test User"
    }
)
print(response.json())

# 2. Login
response = requests.post(
    f"{BASE_URL}/auth/login",
    data={
        "username": "testuser",
        "password": "password123"
    }
)
token = response.json()["access_token"]

# 3. Get current user info
response = requests.get(
    f"{BASE_URL}/auth/me",
    headers={"Authorization": f"Bearer {token}"}
)
print(response.json())
```

## Understanding the Code

### How Authentication Works

1. **Registration** (`POST /auth/register`):
   - User sends email, username, and password
   - Password is hashed using bcrypt (never stored as plain text!)
   - User is saved to the database
   - User info is returned (without password)

2. **Login** (`POST /auth/login`):
   - User sends username/email and password
   - System finds user and verifies password
   - If correct, creates a JWT token
   - Token is returned to the user

3. **Protected Routes** (`GET /auth/me`):
   - User sends token in Authorization header
   - System decodes and validates token
   - User info is extracted from token
   - Route function receives the current user

### Key Concepts

- **Models** (`models/user.py`): Define database structure
- **Schemas** (`schemas/auth.py`): Define API request/response format
- **Routes** (`api/auth.py`): Handle HTTP requests
- **Security** (`utils/security.py`): Password hashing, JWT tokens
- **Dependencies**: FastAPI's way of sharing code between routes

## Database

This starter uses **SQLite** - a simple file-based database perfect for learning. The database file is created automatically as `feature_voting.db` when you first run the server.

### View the Database

```bash
# Install SQLite browser (optional)
# macOS: brew install --cask db-browser-for-sqlite
# Then open feature_voting.db

# Or use command line:
sqlite3 feature_voting.db
# Then: SELECT * FROM users;
```

### Upgrade to PostgreSQL Later

When you're ready, update `.env`:
```
DATABASE_URL=postgresql://username:password@localhost:5432/dbname
```

And update `database.py` to remove the SQLite-specific `connect_args`.

## Common Issues

### Issue: "Module not found"
Make sure your virtual environment is activated:
```bash
source venv/bin/activate  # macOS/Linux
```

### Issue: "Address already in use"
Another process is using port 8000. Either:
- Stop the other process
- Use a different port: `uvicorn app.main:app --reload --port 8001`

### Issue: "Could not validate credentials"
- Make sure you're using the correct token
- Tokens expire after 30 minutes - login again
- Check that you're sending the token in the Authorization header

## Next Steps

Now that you have basic authentication working, you can:

1. **Add More Models**: Create models for ideas, votes, etc.
2. **Add More Routes**: Build endpoints for creating and voting on ideas
3. **Add Tests**: Write tests for your endpoints
4. **Build a Frontend**: Create a React app to interact with this API
5. **Deploy**: Put your app online (Railway, Render, etc.)

## Learning Resources

- **FastAPI Tutorial**: https://fastapi.tiangolo.com/tutorial/
- **SQLAlchemy Basics**: https://docs.sqlalchemy.org/en/20/tutorial/
- **JWT Tokens**: https://jwt.io/introduction
- **HTTP Status Codes**: https://httpstatuses.com/

## Need Help?

- Check the comments in the code - they explain what each part does
- Read the FastAPI docs - they're excellent!
- The `/docs` endpoint shows you exactly what each endpoint expects

Happy coding! 🚀
