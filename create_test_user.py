#!/usr/bin/env python3
"""Create a test user for Module 7 testing"""

import sys
sys.path.append('backend')

from app.database import SessionLocal
from app.models.user import User
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

db = SessionLocal()

# Check if test user exists
existing = db.query(User).filter(User.username == "testuser").first()
if existing:
    print("Test user already exists")
    db.close()
    sys.exit(0)

# Create test user
test_user = User(
    username="testuser",
    email="test@example.com",
    hashed_password=pwd_context.hash("testpass123"),
    is_active=True
)

db.add(test_user)
db.commit()
db.refresh(test_user)

print(f"✅ Created test user: {test_user.username} (ID: {test_user.id})")
print(f"   Username: testuser")
print(f"   Password: testpass123")

db.close()
