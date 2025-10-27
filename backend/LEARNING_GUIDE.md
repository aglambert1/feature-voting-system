# Learning Guide: Understanding Your FastAPI Backend

This guide explains the key concepts in your backend code. Perfect for beginners!

## Table of Contents
1. [The Big Picture](#the-big-picture)
2. [Understanding the Files](#understanding-the-files)
3. [How Authentication Works](#how-authentication-works)
4. [Key Concepts Explained](#key-concepts-explained)
5. [Common Patterns](#common-patterns)

---

## The Big Picture

Your backend is a **REST API** - it receives HTTP requests and sends back JSON responses.

```
Frontend/Client                    Backend (FastAPI)                Database
     │                                    │                            │
     │  1. POST /auth/register           │                            │
     ├───────────────────────────────────>│                            │
     │                                    │  2. Hash password          │
     │                                    │  3. Save user              │
     │                                    ├────────────────────────────>│
     │                                    │  4. User saved             │
     │  5. User data (JSON)               │<────────────────────────────┤
     │<───────────────────────────────────┤                            │
     │                                    │                            │
```

### The Flow:
1. Client sends a request (e.g., "register this user")
2. FastAPI receives it and validates the data
3. Your code processes it (hash password, save to DB, etc.)
4. Response is sent back to the client

---

## Understanding the Files

### 📄 `main.py` - The Heart of Your App

This is where everything starts. It:
- Creates the FastAPI application
- Sets up CORS (so your frontend can talk to it)
- Includes all your routes
- Initializes the database

**Key Line:**
```python
app = FastAPI(title="Feature Voting System")
```
This creates your web application!

---

### ⚙️ `config.py` - Settings Management

Manages all configuration using environment variables.

**Why environment variables?**
- Secrets (like SECRET_KEY) shouldn't be in your code
- Different settings for development vs production
- Easy to change without editing code

**Example:**
```python
class Settings(BaseSettings):
    database_url: str = "sqlite:///./feature_voting.db"
    secret_key: str = "..."
```

---

### 🗄️ `database.py` - Database Connection

Sets up SQLAlchemy to talk to your database.

**Three main things:**

1. **Engine** - The connection to the database
2. **SessionLocal** - A "workspace" for database operations
3. **Base** - Parent class for all your models

**Important Function:**
```python
def get_db():
    db = SessionLocal()
    try:
        yield db  # Give the session to your route
    finally:
        db.close()  # Always clean up!
```

---

### 📊 `models/user.py` - Database Table Definition

This is your **database schema** - it defines what a user looks like in the database.

**Each Column:**
- `id` - Unique identifier (auto-increments)
- `email` - User's email (must be unique)
- `username` - User's username (must be unique)
- `hashed_password` - Encrypted password (never store plain text!)
- `role` - What the user can do (admin, voter, viewer)
- `is_active` - Can disable accounts without deleting
- `created_at` - When the account was created
- `updated_at` - When it was last modified

**The Class:**
```python
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True)
    # ... etc
```

SQLAlchemy automatically creates this table for you!

---

### 📋 `schemas/auth.py` - API Data Shapes

These define what your API accepts and returns.

**Why separate from models?**
- Models = Database structure
- Schemas = API structure
- They're similar but serve different purposes!

**Example:**
```python
class UserCreate(BaseModel):
    email: EmailStr      # Must be valid email
    username: str        # Required string
    password: str        # Min 8 characters
    full_name: Optional[str]  # Optional field
```

**UserResponse** is what you send back - notice it doesn't include the password!

---

### 🔒 `utils/security.py` - The Security Layer

Handles all the security stuff:

**1. Password Hashing**
```python
hash_password("mypassword")
# Returns: "$2b$12$EixZaYVK1fsbw1ZfbX3OXe..."
```
- Passwords are NEVER stored as plain text
- Uses bcrypt (very secure, industry standard)
- Even if someone steals your database, they can't read passwords!

**2. Password Verification**
```python
verify_password("mypassword", hashed_password)
# Returns: True or False
```

**3. JWT Token Creation**
```python
create_access_token(data={"sub": username})
# Returns: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```
- JWT = JSON Web Token
- Contains user info (encrypted and signed)
- Can't be tampered with (we'd detect it)

**4. Getting Current User**
```python
async def get_current_user(token: str, db: Session):
    # Decodes token
    # Finds user in database
    # Returns user object
```

---

### 🛣️ `api/auth.py` - The Routes (Endpoints)

This is where HTTP requests are handled.

#### 1. Register Endpoint

```python
@router.post("/auth/register", response_model=UserResponse)
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    # 1. Check if email exists
    # 2. Check if username exists
    # 3. Hash password
    # 4. Create user
    # 5. Save to database
    # 6. Return user (without password!)
```

**The `@router.post()` decorator:**
- `"/auth/register"` - The URL path
- `response_model=UserResponse` - What to return
- FastAPI automatically validates input and serializes output!

#### 2. Login Endpoint

```python
@router.post("/auth/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm, db: Session):
    # 1. Find user
    # 2. Verify password
    # 3. Create JWT token
    # 4. Return token
```

**OAuth2PasswordRequestForm:**
- Standard format for login (username + password)
- Works with the interactive docs automatically!

#### 3. Get Current User

```python
@router.get("/auth/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user)
):
    return current_user
```

**This is a protected route!**
- Requires a valid token
- `Depends(get_current_active_user)` does all the work
- If token is invalid, FastAPI returns 401 Unauthorized

---

## How Authentication Works

### Step-by-Step: User Registration

1. **Client sends POST request to `/auth/register`**
   ```json
   {
     "email": "user@example.com",
     "username": "johndoe",
     "password": "secretpass123"
   }
   ```

2. **FastAPI validates the data** (is email valid? is password long enough?)

3. **Your code runs:**
   ```python
   # Check if email exists
   existing_user = db.query(User).filter(User.email == user_data.email).first()
   if existing_user:
       raise HTTPException(400, "Email already registered")

   # Hash the password
   hashed = hash_password(user_data.password)

   # Create new user
   new_user = User(email=..., hashed_password=hashed, ...)
   db.add(new_user)
   db.commit()
   ```

4. **Return user data** (password is excluded automatically!)

### Step-by-Step: User Login

1. **Client sends credentials**
   ```
   username: johndoe
   password: secretpass123
   ```

2. **Your code verifies:**
   ```python
   # Find user
   user = db.query(User).filter(User.username == "johndoe").first()

   # Verify password
   if not verify_password("secretpass123", user.hashed_password):
       raise HTTPException(401, "Incorrect password")

   # Create token
   token = create_access_token(data={"sub": user.username})
   ```

3. **Return token:**
   ```json
   {
     "access_token": "eyJhbGciOiJIUzI1NiIs...",
     "token_type": "bearer"
   }
   ```

### Step-by-Step: Accessing Protected Routes

1. **Client sends request with token:**
   ```
   GET /auth/me
   Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
   ```

2. **`get_current_user` dependency runs:**
   ```python
   # Extract token from header
   # Decode and validate token
   # Find user in database
   # Return user object
   ```

3. **Your route receives the user:**
   ```python
   def protected_route(current_user: User = Depends(get_current_user)):
       # current_user is already authenticated!
       return {"username": current_user.username}
   ```

---

## Key Concepts Explained

### Dependencies in FastAPI

Dependencies are a way to share logic between routes.

**Instead of this:**
```python
@app.get("/route1")
def route1(token: str):
    user = verify_token(token)
    # ... use user

@app.get("/route2")
def route2(token: str):
    user = verify_token(token)
    # ... use user
```

**You do this:**
```python
@app.get("/route1")
def route1(user: User = Depends(get_current_user)):
    # ... use user

@app.get("/route2")
def route2(user: User = Depends(get_current_user)):
    # ... use user
```

**Benefits:**
- Write the logic once
- Cleaner code
- Easier to test

### Models vs Schemas

**Models (SQLAlchemy):**
- Represent database tables
- Have database-specific features (foreign keys, indexes, etc.)
- Used for database operations

**Schemas (Pydantic):**
- Represent API data
- Validation and serialization
- Documentation in API docs

**Example:**
```python
# Model - Database
class User(Base):
    id = Column(Integer, primary_key=True)
    email = Column(String)
    hashed_password = Column(String)

# Schema - API
class UserResponse(BaseModel):
    id: int
    email: str
    # No password field! Never expose it via API
```

### Async vs Sync

You'll see both `def` and `async def`:

```python
def sync_function():
    # Runs normally
    pass

async def async_function():
    # Can use 'await' for async operations
    pass
```

**When to use async:**
- Database queries (if using async drivers)
- API calls
- File operations
- Anything that "waits"

**For now:** Both work fine! FastAPI handles it automatically.

---

## Common Patterns

### Pattern 1: Database Query

```python
# Get one user
user = db.query(User).filter(User.id == 1).first()

# Get all users
users = db.query(User).all()

# Get with condition
admin_users = db.query(User).filter(User.role == "admin").all()

# Create
new_user = User(email="...", username="...")
db.add(new_user)
db.commit()
db.refresh(new_user)  # Get the auto-generated ID

# Update
user.email = "newemail@example.com"
db.commit()

# Delete
db.delete(user)
db.commit()
```

### Pattern 2: Error Handling

```python
from fastapi import HTTPException, status

# Return 404 Not Found
if not user:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="User not found"
    )

# Return 400 Bad Request
if invalid_data:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid data"
    )
```

### Pattern 3: Route Definition

```python
@router.post(            # HTTP method
    "/auth/register",    # URL path
    response_model=UserResponse,  # What to return
    status_code=status.HTTP_201_CREATED  # Success code
)
def register(
    user_data: UserCreate,           # Request body
    db: Session = Depends(get_db)    # Database session
):
    # Your code here
    return new_user
```

---

## Next Steps

1. **Experiment!** Change things and see what happens
2. **Add a new field** to the User model
3. **Create a new endpoint** (e.g., GET /users to list all users)
4. **Add more models** (Idea, Vote, etc.)
5. **Read the FastAPI tutorial** for more advanced features

Remember: The best way to learn is by doing! 🚀
