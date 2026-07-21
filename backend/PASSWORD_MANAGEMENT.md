# Password Management API

Complete password management system with OTP-based reset and authenticated password change.

## Features

### 1. Password Reset with OTP
- User requests password reset by providing email
- System generates 6-digit OTP code
- OTP is "sent" to user's email (MVP: logged to console)
- OTP expires after 15 minutes
- OTP can only be used once
- User provides OTP + new password to complete reset

### 2. Password Change (Authenticated)
- User must be logged in
- Must provide current password for verification
- New password must be different from current
- Email notification sent after change

## API Endpoints

### POST /auth/password/reset-request

Request a password reset OTP.

**Authentication:** None (public endpoint)

**Request Body:**
```json
{
  "email": "user@example.com"
}
```

**Response (200 OK):**
```json
{
  "message": "If this email is registered, you will receive a password reset code.",
  "detail": "Check your email for the OTP code. It expires in 15 minutes."
}
```

**Notes:**
- Returns success even if email doesn't exist (prevents email enumeration)
- Only sends OTP if email exists in database
- Invalidates any previous unused OTPs for this user
- In MVP: OTP is printed to console/logs instead of email

---

### POST /auth/password/reset-confirm

Confirm password reset with OTP.

**Authentication:** None (public endpoint)

**Request Body:**
```json
{
  "email": "user@example.com",
  "otp": "123456",
  "new_password": "NewSecurePassword123"
}
```

**Response (200 OK):**
```json
{
  "message": "Password successfully reset",
  "detail": "You can now log in with your new password."
}
```

**Errors:**
- `404`: User not found
- `400`: Invalid or already used OTP
- `400`: OTP expired
- `422`: Validation error (invalid email format, password too short, etc.)

**Notes:**
- OTP must be exactly 6 digits
- OTP can only be used once
- Password must be 8-100 characters
- Sends email notification after successful reset

---

### POST /auth/password/change

Change password (requires authentication).

**Authentication:** Required (Bearer token)

**Request Body:**
```json
{
  "current_password": "OldPassword123",
  "new_password": "NewSecurePassword456"
}
```

**Response (200 OK):**
```json
{
  "message": "Password successfully changed",
  "detail": "Your password has been updated."
}
```

**Errors:**
- `401`: Not authenticated
- `400`: Current password incorrect
- `400`: New password same as current password
- `422`: Validation error

**Notes:**
- Must provide valid JWT token in Authorization header
- Must provide correct current password
- New password must be different from current
- Sends email notification after successful change

## Database Schema

### password_reset_tokens table

```sql
CREATE TABLE password_reset_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    token VARCHAR NOT NULL,          -- 6-digit OTP
    expires_at DATETIME NOT NULL,     -- Expiration time (15 min from creation)
    is_used BOOLEAN DEFAULT FALSE,    -- Has token been used?
    created_at DATETIME DEFAULT NOW,
    used_at DATETIME                  -- When was it used?
);
```

## Security Features

### 1. Email Enumeration Prevention
- Password reset request always returns success
- Doesn't reveal if email exists in database
- Only sends OTP if email is registered

### 2. OTP Security
- 6-digit random numeric code
- Expires after 15 minutes
- Can only be used once
- Previous unused tokens invalidated on new request

### 3. Password Change Security
- Requires authentication (JWT token)
- Requires current password verification
- New password must be different from current

### 4. Email Notifications
- Notification sent after password reset
- Notification sent after password change
- Alerts user to unauthorized changes

## Email Service

Sent via SendGrid in production (`sendgrid_api_key` / `sendgrid_from_email` in config); falls back to console logging in local dev when no SendGrid key is set. See [DEV_MODE_OTP.md](DEV_MODE_OTP.md) for local-dev OTP workarounds.

## Testing

### Run Tests

```bash
cd backend
source venv/bin/activate
python test_password_management.py
```

### Test Flow

1. Creates test user
2. Requests password reset
3. Retrieves OTP from console
4. Confirms reset with OTP
5. Verifies new password works
6. Changes password while authenticated
7. Tests all security validations

### Interactive Testing (Swagger UI)

1. Open: http://localhost:8000/docs
2. Find password endpoints under "Authentication"
3. Try each endpoint:
   - POST /auth/password/reset-request
   - POST /auth/password/reset-confirm
   - POST /auth/password/change

## Example Usage

### Scenario 1: Forgot Password

```python
import requests

BASE_URL = "http://localhost:8000"

# Step 1: Request reset
response = requests.post(
    f"{BASE_URL}/auth/password/reset-request",
    json={"email": "user@example.com"}
)
# Check console for OTP code

# Step 2: Confirm with OTP
response = requests.post(
    f"{BASE_URL}/auth/password/reset-confirm",
    json={
        "email": "user@example.com",
        "otp": "123456",  # From console
        "new_password": "NewPassword123"
    }
)

# Step 3: Login with new password
response = requests.post(
    f"{BASE_URL}/auth/login",
    data={
        "username": "user@example.com",
        "password": "NewPassword123"
    }
)
token = response.json()["access_token"]
```

### Scenario 2: Change Password (Logged In)

```python
# Already logged in with token
headers = {"Authorization": f"Bearer {token}"}

response = requests.post(
    f"{BASE_URL}/auth/password/change",
    json={
        "current_password": "OldPassword123",
        "new_password": "NewSecurePassword456"
    },
    headers=headers
)
```

## Configuration

Add to `backend/.env`:

```env
# Email settings (for production)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
FROM_EMAIL=noreply@yourapp.com

# Or use SendGrid
SENDGRID_API_KEY=SG.xxxxx

# Or use AWS SES
AWS_ACCESS_KEY_ID=xxxxx
AWS_SECRET_ACCESS_KEY=xxxxx
AWS_REGION=us-east-1
```

## Validation Rules

### Email
- Must be valid email format
- Required for reset request and confirmation

### OTP
- Must be exactly 6 digits
- Must match stored token
- Must not be expired
- Must not have been used

### Password
- Minimum 8 characters
- Maximum 100 characters
- No other complexity requirements (add as needed)

## Error Handling

All endpoints return clear error messages:

```json
{
  "detail": "Current password is incorrect"
}
```

```json
{
  "detail": "OTP code has expired. Please request a new one."
}
```

## Related Auth Features (Shipped Since This Doc Was Written)

These live in `app/api/auth.py` / `app/models/user.py` and aren't covered above:

- **Password strength validation** — `_validate_password_strength()` in `app/schemas/auth.py`, applied to registration, reset-confirm, and change
- **Account lockout** — 5 failed logins within 15 minutes locks the account; admin unlock via `POST /users/{id}/unlock`
- **Session invalidation** — `tokens_valid_after` on the user record; admin password resets and unlocks invalidate all existing JWTs
- **Optional TOTP MFA** — users enable/disable from Profile > Security; adds a second login step when active (separate from password reset)
- **Admin-initiated password reset** — an admin can force-reset a user's password, which also invalidates existing sessions

## Future Enhancements

- **Email Templates** — HTML/branded emails, multi-language support
- **Password History** — prevent reusing last N passwords, track change history

## Files Created

```
backend/
├── app/
│   ├── models/
│   │   └── password_reset.py        # PasswordResetToken model
│   ├── schemas/
│   │   └── auth.py                  # Added password schemas
│   ├── api/
│   │   └── auth.py                  # Added 3 endpoints
│   └── utils/
│       ├── email.py                 # Email service (MVP)
│       └── otp.py                   # OTP generation
├── test_password_management.py      # Comprehensive tests
└── PASSWORD_MANAGEMENT.md           # This file
```

## Support

For issues or questions:
1. Check server logs for OTP codes (MVP mode)
2. Verify database has password_reset_tokens table
3. Ensure user exists before testing reset
4. Check token expiration (15 minutes)

---

**Created:** 2025-10-31
**Status:** Complete and tested
