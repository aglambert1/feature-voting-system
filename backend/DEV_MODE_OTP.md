# Development Mode OTP Workaround

## Problem
In development environments without a mail server, OTP-based password recovery is difficult to test because:
- OTPs are only logged to the console
- Developers need to constantly check console logs
- Testing password reset flows is cumbersome

## Solution
This implementation provides **three development mode workarounds** to easily test OTP functionality without an email server:

### 1. Fixed Development OTP (Universal Bypass)
A hardcoded OTP that always works in development mode.

**Default:** `000000`

**How to use:**
```bash
# Step 1: Request password reset (optional, just to be realistic)
curl -X POST http://localhost:8000/auth/password/reset-request \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com"}'

# Step 2: Reset password with fixed dev OTP
curl -X POST http://localhost:8000/auth/password/reset-confirm \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@example.com",
    "otp": "000000",
    "new_password": "newpassword123"
  }'
```

### 2. OTP Returned in API Response
When `DEBUG=true` and `DEV_RETURN_OTP=true`, the actual OTP is included in the password reset request response.

**How to use:**
```bash
# Request password reset - response includes the OTP!
curl -X POST http://localhost:8000/auth/password/reset-request \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com"}'

# Response:
# {
#   "message": "If this email is registered, you will receive a password reset code.",
#   "detail": "[DEV MODE] OTP: 123456 | Expires in 15 minutes. Also logged to console.",
#   "dev_otp": "123456"
# }

# Use the returned OTP to reset password
curl -X POST http://localhost:8000/auth/password/reset-confirm \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@example.com",
    "otp": "123456",
    "new_password": "newpassword123"
  }'
```

### 3. Development Endpoint to Retrieve OTP
A special endpoint that returns the latest OTP for any email address.

**Endpoint:** `GET /auth/dev/get-otp/{email}`

**How to use:**
```bash
# Step 1: Request password reset
curl -X POST http://localhost:8000/auth/password/reset-request \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com"}'

# Step 2: Retrieve the OTP using the dev endpoint
curl http://localhost:8000/auth/dev/get-otp/admin@example.com

# Response:
# {
#   "email": "admin@example.com",
#   "otp": "123456",
#   "expires_at": "2024-01-15T12:30:00",
#   "message": "Active OTP found. Fixed dev bypass OTP is also available: 000000"
# }

# Step 3: Use the OTP to reset password
curl -X POST http://localhost:8000/auth/password/reset-confirm \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@example.com",
    "otp": "123456",
    "new_password": "newpassword123"
  }'
```

## Configuration

### Environment Variables

Add these to your `.env` file:

```bash
# Enable development mode
DEBUG=true

# Development OTP Settings
DEV_OTP_BYPASS=000000              # Fixed OTP that always works (default: "000000")
DEV_RETURN_OTP=true                # Return OTP in API response (default: true)
```

### Configuration in `app/config.py`

```python
class Settings(BaseSettings):
    debug: bool = True

    # Development mode settings for OTP bypass
    # SECURITY WARNING: Only use in development! Never enable in production!
    dev_otp_bypass: str = "000000"  # Fixed OTP that always works in debug mode
    dev_return_otp: bool = True     # Return OTP in API response when debug=True
```

## Security Considerations

### ⚠️ CRITICAL SECURITY WARNINGS

1. **Never use in production!**
   - Set `DEBUG=false` in production
   - The dev bypass OTP only works when `DEBUG=true`
   - The dev endpoint is automatically disabled when `DEBUG=false`

2. **Automatic safeguards:**
   - Fixed dev OTP (`000000`) only accepted when `debug=True`
   - Development endpoint returns 403 Forbidden when `debug=False`
   - OTP is only included in response when both `debug=True` AND `dev_return_otp=True`

3. **Best practices:**
   - Use different `.env` files for development and production
   - Never commit `.env` files to version control
   - Always verify `DEBUG=false` before deploying to production

## Testing the Features

### Quick Test Script

```bash
#!/bin/bash

BASE_URL="http://localhost:8000"
EMAIL="admin@example.com"
DEV_OTP="000000"

echo "=== Testing Development Mode OTP Features ==="

echo -e "\n1. Testing Fixed Dev OTP Bypass..."
echo "   Requesting password reset..."
curl -X POST $BASE_URL/auth/password/reset-request \
  -H "Content-Type: application/json" \
  -d "{\"email\": \"$EMAIL\"}" 2>/dev/null

echo -e "\n   Resetting password with dev bypass OTP..."
curl -X POST $BASE_URL/auth/password/reset-confirm \
  -H "Content-Type: application/json" \
  -d "{\"email\": \"$EMAIL\", \"otp\": \"$DEV_OTP\", \"new_password\": \"TestPassword123\"}" 2>/dev/null

echo -e "\n\n2. Testing OTP in Response..."
RESPONSE=$(curl -s -X POST $BASE_URL/auth/password/reset-request \
  -H "Content-Type: application/json" \
  -d "{\"email\": \"$EMAIL\"}")
echo "$RESPONSE" | python -m json.tool

echo -e "\n\n3. Testing Dev Endpoint..."
curl $BASE_URL/auth/dev/get-otp/$EMAIL 2>/dev/null | python -m json.tool

echo -e "\n\n=== Tests Complete ==="
```

Save this as `test_dev_otp.sh` and run:
```bash
chmod +x test_dev_otp.sh
./test_dev_otp.sh
```

## Implementation Details

### Files Modified

1. **`app/config.py`**
   - Added `dev_otp_bypass` setting (default: "000000")
   - Added `dev_return_otp` setting (default: True)

2. **`app/schemas/auth.py`**
   - Added `PasswordResetResponse` schema with optional `dev_otp` field
   - Added `DevOTPResponse` schema for dev endpoint

3. **`app/api/auth.py`**
   - Modified `/password/reset-request` to return OTP in debug mode
   - Modified `/password/reset-confirm` to accept fixed dev OTP in debug mode
   - Added `/dev/get-otp/{email}` development endpoint

4. **`.env.example`**
   - Added documentation for `DEV_OTP_BYPASS` and `DEV_RETURN_OTP`

### Code Flow

**Password Reset Request (with dev mode):**
```python
# When debug=True and dev_return_otp=True
response = PasswordResetResponse(
    message="...",
    detail=f"[DEV MODE] OTP: {otp} | Expires in 15 minutes.",
    dev_otp=otp  # Only included in debug mode
)
```

**Password Reset Confirm (with dev bypass):**
```python
# Accept fixed dev OTP when debug=True
if settings.debug and request.otp == settings.dev_otp_bypass:
    # Skip database validation, allow password reset
    is_dev_bypass = True
```

## Recommendations

### For Development
Choose the method that works best for your workflow:

- **Fixed OTP (`000000`)**: Fastest for quick testing, no need to check anything
- **OTP in Response**: Good for automated testing and scripts
- **Dev Endpoint**: Best for debugging, can retrieve OTP anytime

### For Testing
When writing tests, use the fixed dev OTP for simplicity:

```python
def test_password_reset_with_dev_otp():
    response = client.post("/auth/password/reset-confirm", json={
        "email": "test@example.com",
        "otp": "000000",  # Fixed dev OTP
        "new_password": "NewPassword123"
    })
    assert response.status_code == 200
```

### For Production Deployment
Before deploying to production, verify:

```bash
# Check your production .env file
grep DEBUG .env  # Should be: DEBUG=false

# Verify dev endpoint is disabled
curl https://your-production-url.com/auth/dev/get-otp/test@example.com
# Should return: 403 Forbidden
```

## Troubleshooting

### Dev OTP not working?
- Check `DEBUG=true` in your `.env`
- Check `DEV_OTP_BYPASS=000000` is set correctly
- Restart the backend server after changing `.env`

### OTP not returned in response?
- Check both `DEBUG=true` AND `DEV_RETURN_OTP=true`
- Restart the backend server after changes

### Dev endpoint returns 403?
- This is correct if `DEBUG=false`
- Set `DEBUG=true` for development

## Conclusion

These development mode features make it easy to test OTP-based password recovery without setting up an email server. The fixed dev OTP (`000000`) is the simplest solution for most development scenarios.

Remember: **Always disable debug mode in production!**
