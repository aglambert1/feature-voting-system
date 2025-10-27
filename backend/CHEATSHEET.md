# FastAPI Backend Cheat Sheet

Quick reference for common tasks and patterns.

## Server Commands

```bash
# Start development server
uvicorn app.main:app --reload

# Start on different port
uvicorn app.main:app --reload --port 8001

# Start with specific host
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run without auto-reload (production)
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Database Commands

```bash
# View database
sqlite3 feature_voting.db

# In SQLite shell:
.tables                 # List all tables
.schema users          # Show table structure
SELECT * FROM users;   # Query users
.exit                  # Exit SQLite
```

## Testing Commands

```bash
# Run test script
python test_api.py

# Install pytest (for future tests)
pip install pytest pytest-asyncio

# Run tests
pytest

# Run with coverage
pytest --cov=app tests/
```

## Python/Environment Commands

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate              # macOS/Linux
venv\Scripts\activate                 # Windows

# Deactivate
deactivate

# Install requirements
pip install -r requirements.txt

# Update requirements
pip freeze > requirements.txt

# Install single package
pip install package-name
```

## Git Commands (Reference)

```bash
# Initialize git (if not already)
git init

# Add files
git add .
git add backend/

# Commit
git commit -m "Add basic authentication"

# View status
git status

# View changes
git diff
```

## Common Code Patterns

### Adding a New Route

```python
# In api/auth.py or create new file
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db

router = APIRouter(prefix="/your-prefix", tags=["Your Tag"])

@router.get("/your-endpoint")
def your_function(db: Session = Depends(get_db)):
    # Your logic here
    return {"message": "Success"}

# Don't forget to include in main.py:
# from app.api import your_new_file
# app.include_router(your_new_file.router)
```

### Adding a Protected Route

```python
from app.utils.security import get_current_active_user
from app.models.user import User

@router.get("/protected")
def protected_route(current_user: User = Depends(get_current_active_user)):
    # current_user is automatically validated
    return {"username": current_user.username}
```

### Database Queries

```python
# Get all
users = db.query(User).all()

# Get one by ID
user = db.query(User).filter(User.id == 1).first()

# Get one by field
user = db.query(User).filter(User.email == "user@example.com").first()

# Get with multiple conditions
user = db.query(User).filter(
    User.email == "user@example.com",
    User.is_active == True
).first()

# Count
count = db.query(User).count()

# Order by
users = db.query(User).order_by(User.created_at.desc()).all()

# Limit
users = db.query(User).limit(10).all()

# Create
new_user = User(email="...", username="...")
db.add(new_user)
db.commit()
db.refresh(new_user)  # Get the ID and other defaults

# Update
user = db.query(User).filter(User.id == 1).first()
user.email = "newemail@example.com"
db.commit()

# Delete
user = db.query(User).filter(User.id == 1).first()
db.delete(user)
db.commit()
```

### Creating a New Model

```python
# In models/your_model.py
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class YourModel(Base):
    __tablename__ = "your_table"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)

    # Foreign key example
    user_id = Column(Integer, ForeignKey("users.id"))
    user = relationship("User")

# Don't forget to import in models/__init__.py
# from app.models.your_model import YourModel
```

### Creating a Schema

```python
# In schemas/your_schema.py
from pydantic import BaseModel
from typing import Optional

class YourModelCreate(BaseModel):
    """For creating (POST requests)"""
    name: str
    description: Optional[str] = None

class YourModelUpdate(BaseModel):
    """For updating (PUT/PATCH requests)"""
    name: Optional[str] = None
    description: Optional[str] = None

class YourModelResponse(BaseModel):
    """For responses (GET requests)"""
    id: int
    name: str
    description: Optional[str]

    class Config:
        from_attributes = True  # Work with SQLAlchemy models
```

### Error Handling

```python
from fastapi import HTTPException, status

# Not found (404)
if not item:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Item not found"
    )

# Bad request (400)
if invalid_data:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid data"
    )

# Unauthorized (401)
if not authenticated:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"}
    )

# Forbidden (403)
if not authorized:
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Not authorized"
    )

# Custom error with details
raise HTTPException(
    status_code=400,
    detail={
        "error": "validation_error",
        "message": "Email already exists",
        "field": "email"
    }
)
```

### Request Body Examples

```python
from pydantic import BaseModel
from typing import List, Optional

# Simple
class SimpleRequest(BaseModel):
    name: str
    age: int

# With validation
class ValidatedRequest(BaseModel):
    email: EmailStr  # Must be valid email
    username: str = Field(..., min_length=3, max_length=50)
    age: int = Field(..., ge=0, le=150)  # 0 <= age <= 150

# With optional fields
class OptionalRequest(BaseModel):
    required_field: str
    optional_field: Optional[str] = None

# With lists
class ListRequest(BaseModel):
    items: List[str]

# With nested objects
class Address(BaseModel):
    street: str
    city: str

class UserWithAddress(BaseModel):
    name: str
    address: Address
```

### Response Models

```python
from typing import List

# Single item
@router.get("/item/{id}", response_model=ItemResponse)
def get_item(id: int):
    return item

# List of items
@router.get("/items", response_model=List[ItemResponse])
def get_items():
    return items

# Custom response
@router.get("/custom")
def custom():
    return {
        "success": True,
        "data": {"key": "value"},
        "message": "Operation successful"
    }
```

## Environment Variables

```bash
# .env file format
KEY=value
DATABASE_URL=sqlite:///./database.db
SECRET_KEY=your-secret-key

# No spaces around =
# No quotes needed (usually)
# Comments with #
```

## HTTP Status Codes

```python
from fastapi import status

status.HTTP_200_OK              # Success
status.HTTP_201_CREATED         # Created successfully
status.HTTP_204_NO_CONTENT      # Success, no content to return

status.HTTP_400_BAD_REQUEST     # Invalid request
status.HTTP_401_UNAUTHORIZED    # Not authenticated
status.HTTP_403_FORBIDDEN       # Not authorized
status.HTTP_404_NOT_FOUND       # Resource not found
status.HTTP_409_CONFLICT        # Conflict (e.g., duplicate)
status.HTTP_422_UNPROCESSABLE_ENTITY  # Validation error

status.HTTP_500_INTERNAL_SERVER_ERROR  # Server error
```

## Testing with curl

```bash
# GET request
curl http://localhost:8000/endpoint

# POST request with JSON
curl -X POST http://localhost:8000/endpoint \
  -H "Content-Type: application/json" \
  -d '{"key": "value"}'

# With authentication
curl http://localhost:8000/protected \
  -H "Authorization: Bearer your-token-here"

# Form data (for login)
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=user&password=pass"

# Pretty print JSON response
curl http://localhost:8000/endpoint | python -m json.tool
```

## Testing with Python requests

```python
import requests

BASE_URL = "http://localhost:8000"

# GET
response = requests.get(f"{BASE_URL}/endpoint")
data = response.json()

# POST
response = requests.post(
    f"{BASE_URL}/endpoint",
    json={"key": "value"}
)

# With headers
response = requests.get(
    f"{BASE_URL}/protected",
    headers={"Authorization": f"Bearer {token}"}
)

# Form data
response = requests.post(
    f"{BASE_URL}/login",
    data={"username": "user", "password": "pass"}
)

# Check status
if response.status_code == 200:
    print("Success!")
else:
    print(f"Error: {response.status_code}")
    print(response.json())
```

## Common Issues & Solutions

### "Module not found"
```bash
# Make sure venv is activated
source venv/bin/activate

# Reinstall requirements
pip install -r requirements.txt
```

### "Address already in use"
```bash
# Find process using port 8000
lsof -i :8000  # macOS/Linux
netstat -ano | findstr :8000  # Windows

# Kill process or use different port
uvicorn app.main:app --reload --port 8001
```

### "Could not import app"
```bash
# Make sure you're in the backend directory
cd backend
uvicorn app.main:app --reload
```

### "Database locked"
```bash
# Close any other connections to the database
# Or use PostgreSQL (doesn't have this issue)
```

### "CORS errors in browser"
```python
# Check allowed_origins in config.py
# Make sure your frontend URL is listed
allowed_origins: list[str] = [
    "http://localhost:3000",
    "http://localhost:5173"
]
```

## Useful Python One-Liners

```bash
# Generate secret key
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Start Python shell with app context
python -c "from app.database import SessionLocal; from app.models import User; db = SessionLocal(); users = db.query(User).all(); print(users)"

# Pretty print JSON
echo '{"key":"value"}' | python -m json.tool

# Create __init__.py files
touch app/new_folder/__init__.py
```

## Documentation URLs

When server is running:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- OpenAPI JSON: http://localhost:8000/openapi.json

## Next Steps Checklist

- [ ] Start the server and test all endpoints
- [ ] Read through all the code comments
- [ ] Try adding a new endpoint
- [ ] Create a new model and schema
- [ ] Test with the interactive docs
- [ ] Run the test script
- [ ] Build a simple frontend to use the API

---

Keep this file handy - you'll reference it often! 📖
