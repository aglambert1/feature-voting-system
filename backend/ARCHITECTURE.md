# Backend Architecture Overview

This document explains how your FastAPI backend is organized.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Client (Browser/App)                  │
│                                                           │
│  Sends HTTP requests (GET, POST, etc.)                  │
│  Receives JSON responses                                 │
└────────────────────┬────────────────────────────────────┘
                     │
                     │ HTTP/JSON
                     │
┌────────────────────▼────────────────────────────────────┐
│                  FastAPI Application                     │
│                                                           │
│  ┌───────────────────────────────────────────────────┐  │
│  │              main.py (Entry Point)                │  │
│  │  - Initializes FastAPI                            │  │
│  │  - Sets up CORS                                   │  │
│  │  - Includes routers                               │  │
│  └───────────────────────────────────────────────────┘  │
│                                                           │
│  ┌───────────────────────────────────────────────────┐  │
│  │         API Routes (api/auth.py)                  │  │
│  │  - POST /auth/register                            │  │
│  │  - POST /auth/login                               │  │
│  │  - GET  /auth/me                                  │  │
│  └───────────────────────────────────────────────────┘  │
│                     │                                     │
│                     ▼                                     │
│  ┌───────────────────────────────────────────────────┐  │
│  │       Business Logic (utils/security.py)          │  │
│  │  - Hash passwords                                 │  │
│  │  - Verify passwords                               │  │
│  │  - Create JWT tokens                              │  │
│  │  - Validate JWT tokens                            │  │
│  └───────────────────────────────────────────────────┘  │
│                     │                                     │
│                     ▼                                     │
│  ┌───────────────────────────────────────────────────┐  │
│  │      Data Layer (models/user.py)                  │  │
│  │  - User model definition                          │  │
│  │  - SQLAlchemy ORM                                 │  │
│  └───────────────────────────────────────────────────┘  │
└────────────────────┬────────────────────────────────────┘
                     │
                     │ SQL Queries
                     │
┌────────────────────▼────────────────────────────────────┐
│              SQLite Database                             │
│                                                           │
│  ┌─────────────────────────────────────────────────┐    │
│  │                 users table                      │    │
│  ├──────────┬──────────┬──────────┬─────────────┐  │    │
│  │ id (PK)  │ email    │ username │ hashed_pwd  │  │    │
│  ├──────────┼──────────┼──────────┼─────────────┤  │    │
│  │ 1        │ u@e.com  │ user1    │ $2b$12$...  │  │    │
│  │ 2        │ a@e.com  │ admin    │ $2b$12$...  │  │    │
│  └──────────┴──────────┴──────────┴─────────────┘  │    │
└─────────────────────────────────────────────────────────┘
```

## Request Flow: User Registration

```
1. Client
   │
   │ POST /auth/register
   │ {
   │   "email": "user@example.com",
   │   "username": "johndoe",
   │   "password": "secret123"
   │ }
   │
   ▼
2. main.py
   │
   │ Routes request to auth router
   │
   ▼
3. api/auth.py → register()
   │
   │ a) Validates data with UserCreate schema
   │ b) Checks if email exists
   │ c) Checks if username exists
   │
   ▼
4. utils/security.py → hash_password()
   │
   │ password "secret123" → "$2b$12$EixZaYVK..."
   │
   ▼
5. models/user.py
   │
   │ Create User object
   │
   ▼
6. database.py → db.add(), db.commit()
   │
   │ INSERT INTO users ...
   │
   ▼
7. SQLite Database
   │
   │ User saved!
   │
   ▼
8. Response to Client
   │
   │ {
   │   "id": 1,
   │   "email": "user@example.com",
   │   "username": "johndoe",
   │   "role": "voter",
   │   "is_active": true,
   │   "created_at": "2024-01-20T10:30:00"
   │ }
   │ (Note: password NOT included!)
```

## Request Flow: User Login

```
1. Client
   │
   │ POST /auth/login
   │ username=johndoe&password=secret123
   │
   ▼
2. api/auth.py → login()
   │
   │ a) Find user by username
   │
   ▼
3. database.py → db.query()
   │
   │ SELECT * FROM users WHERE username = 'johndoe'
   │
   ▼
4. utils/security.py → verify_password()
   │
   │ Compare "secret123" with "$2b$12$..."
   │ ✓ Match!
   │
   ▼
5. utils/security.py → create_access_token()
   │
   │ Create JWT token:
   │ {
   │   "sub": "johndoe",
   │   "user_id": 1,
   │   "exp": 1234567890
   │ }
   │ Encode with SECRET_KEY
   │
   ▼
6. Response to Client
   │
   │ {
   │   "access_token": "eyJhbGciOiJIUzI1NiIs...",
   │   "token_type": "bearer"
   │ }
```

## Request Flow: Protected Route

```
1. Client
   │
   │ GET /auth/me
   │ Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
   │
   ▼
2. utils/security.py → oauth2_scheme
   │
   │ Extract token from Authorization header
   │
   ▼
3. utils/security.py → get_current_user()
   │
   │ a) Decode JWT token
   │    eyJhbGciOiJIUzI1NiIs... → {"sub": "johndoe", ...}
   │
   │ b) Validate signature (is it tampered?)
   │ c) Check expiration (is it expired?)
   │
   ▼
4. database.py → db.query()
   │
   │ SELECT * FROM users WHERE username = 'johndoe'
   │
   ▼
5. api/auth.py → get_current_user_info()
   │
   │ Receives User object
   │ current_user = <User id=1 username='johndoe'>
   │
   ▼
6. Response to Client
   │
   │ {
   │   "id": 1,
   │   "email": "user@example.com",
   │   "username": "johndoe",
   │   "role": "voter",
   │   ...
   │ }
```

## File Organization

```
backend/
│
├── app/                          # Main application package
│   │
│   ├── __init__.py               # Package marker
│   │
│   ├── main.py                   # 🎯 START HERE - Application entry point
│   │   └── Creates FastAPI app
│   │   └── Configures CORS
│   │   └── Includes routers
│   │   └── Initializes database
│   │
│   ├── config.py                 # ⚙️ Configuration management
│   │   └── Loads environment variables
│   │   └── Settings class
│   │
│   ├── database.py               # 🗄️ Database connection
│   │   └── SQLAlchemy engine
│   │   └── Session factory
│   │   └── get_db() dependency
│   │
│   ├── models/                   # 📊 Database models
│   │   ├── __init__.py
│   │   └── user.py               # User table definition
│   │       └── User class (SQLAlchemy)
│   │       └── UserRole enum
│   │
│   ├── schemas/                  # 📋 Pydantic schemas
│   │   ├── __init__.py
│   │   └── auth.py               # Request/response formats
│   │       └── UserCreate - for registration
│   │       └── UserLogin - for login
│   │       └── UserResponse - for returning user data
│   │       └── Token - for JWT token response
│   │
│   ├── api/                      # 🛣️ API routes
│   │   ├── __init__.py
│   │   └── auth.py               # Authentication endpoints
│   │       └── POST /auth/register
│   │       └── POST /auth/login
│   │       └── GET  /auth/me
│   │
│   └── utils/                    # 🔧 Utility functions
│       ├── __init__.py
│       └── security.py           # Security utilities
│           └── hash_password()
│           └── verify_password()
│           └── create_access_token()
│           └── get_current_user()
│
├── requirements.txt              # 📦 Python dependencies
├── .env.example                  # 📝 Example environment variables
├── .gitignore                    # 🚫 Git ignore rules
├── README.md                     # 📖 Main documentation
├── QUICKSTART.md                 # 🚀 Quick start guide
├── LEARNING_GUIDE.md             # 📚 Learning guide
├── ARCHITECTURE.md               # 🏗️ This file!
└── test_api.py                   # 🧪 API test script
```

## Data Flow Diagram

```
┌────────────┐
│   Client   │ "I want to register"
└─────┬──────┘
      │
      │ HTTP POST /auth/register
      │ {"email": "...", "username": "...", "password": "..."}
      │
      ▼
┌────────────────┐
│   FastAPI      │ "Let me validate this data"
│   (main.py)    │
└─────┬──────────┘
      │
      │ Routes to auth.register()
      │
      ▼
┌────────────────┐
│  Auth Router   │ "Is this data valid?"
│  (api/auth.py) │
└─────┬──────────┘
      │
      ├─── Check email exists? ────> Database Query
      │
      ├─── Check username exists? ──> Database Query
      │
      ▼
┌────────────────┐
│   Security     │ "Let me secure that password"
│ (utils/        │
│  security.py)  │
└─────┬──────────┘
      │
      │ hash_password("secret123")
      │ returns "$2b$12$..."
      │
      ▼
┌────────────────┐
│  User Model    │ "Create the user object"
│ (models/       │
│  user.py)      │
└─────┬──────────┘
      │
      │ User(email=..., hashed_password=...)
      │
      ▼
┌────────────────┐
│   Database     │ "Save it!"
│                │
└─────┬──────────┘
      │
      │ INSERT INTO users ...
      │
      ▼
┌────────────────┐
│  UserResponse  │ "Format the response"
│  Schema        │
└─────┬──────────┘
      │
      │ Remove sensitive fields (password)
      │ Convert to JSON
      │
      ▼
┌────────────────┐
│   Client       │ "Success! Here's your user data"
└────────────────┘
```

## Security Layers

```
┌────────────────────────────────────────────────────────┐
│                  Layer 1: CORS                          │
│  Only specified origins can access the API              │
└────────────────────────────────────────────────────────┘
                         │
┌────────────────────────▼───────────────────────────────┐
│              Layer 2: Data Validation                   │
│  Pydantic schemas validate all input data               │
└────────────────────────────────────────────────────────┘
                         │
┌────────────────────────▼───────────────────────────────┐
│           Layer 3: Password Hashing                     │
│  Passwords are hashed with bcrypt (very secure)         │
└────────────────────────────────────────────────────────┘
                         │
┌────────────────────────▼───────────────────────────────┐
│              Layer 4: JWT Tokens                        │
│  Signed tokens that can't be tampered with              │
└────────────────────────────────────────────────────────┘
                         │
┌────────────────────────▼───────────────────────────────┐
│        Layer 5: Authentication Dependencies             │
│  Protected routes require valid tokens                  │
└────────────────────────────────────────────────────────┘
```

## Key Technologies

| Technology    | Purpose                           | Why We Use It                |
|---------------|-----------------------------------|------------------------------|
| **FastAPI**   | Web framework                     | Fast, modern, automatic docs |
| **SQLAlchemy**| Database ORM                      | Work with DB using Python    |
| **Pydantic**  | Data validation                   | Automatic validation & docs  |
| **Uvicorn**   | ASGI server                       | Runs the FastAPI app         |
| **JWT**       | Authentication tokens             | Stateless authentication     |
| **bcrypt**    | Password hashing                  | Industry-standard security   |
| **SQLite**    | Database                          | Simple, file-based           |

## Configuration Flow

```
.env file
    │
    │ SECRET_KEY=abc123
    │ DATABASE_URL=sqlite:///...
    │
    ▼
config.py
    │
    │ class Settings(BaseSettings):
    │     secret_key: str
    │     database_url: str
    │
    ▼
settings = Settings()
    │
    │ Reads from .env
    │ Validates types
    │
    ▼
Used throughout app
    │
    ├──> database.py (uses database_url)
    ├──> security.py (uses secret_key)
    └──> main.py (uses allowed_origins)
```

## What Happens When Server Starts

```
1. python -m uvicorn app.main:app --reload
   │
   │
2. Uvicorn loads app from app/main.py
   │
   ├──> FastAPI app is created
   │    │
   │    ├──> CORS middleware added
   │    ├──> Auth router included
   │    └──> Startup event registered
   │
   ▼
3. Startup event runs
   │
   └──> init_db() creates tables
        │
        └──> SQLite database file created (if not exists)
             │
             └──> 'users' table created
   │
   ▼
4. Server ready!
   │
   └──> Listening on http://127.0.0.1:8000
```

## Next Steps

Now that you understand the architecture:

1. **Trace a request** - Follow the code from route to database and back
2. **Add a new endpoint** - Practice the pattern
3. **Add a new model** - Create an Idea or Vote model
4. **Read the code** - The comments explain everything!

Remember: This is a solid foundation. Everything else follows these same patterns! 🎉
