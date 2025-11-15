# Authentication System Guide

Complete guide to the authentication system implementation.

## Overview

The authentication system provides secure user registration, login, and token-based authentication using industry-standard practices:

- **Password Security**: bcrypt hashing with automatic salt generation
- **Token Authentication**: JWT (JSON Web Tokens) with access and refresh tokens
- **Credential Encryption**: Fernet symmetric encryption for storing sensitive data
- **FastAPI Integration**: Dependency injection for protecting routes

## Architecture

### Components

```
Security Layer
├── password.py         # bcrypt password hashing and verification
├── jwt.py              # JWT token creation and verification
├── encryption.py       # Fernet credential encryption
└── dependencies.py     # FastAPI authentication dependencies

API Layer
└── api/auth.py         # Authentication endpoints

Schemas
└── schemas/auth.py     # Pydantic models for validation

Models
└── models/user.py      # SQLAlchemy User model
```

### Security Flow

```
Registration:
User submits email + password
→ Validate password strength (8+ chars, letter + digit)
→ Hash password with bcrypt
→ Store user with hash + salt
→ Generate JWT tokens
→ Return tokens + user info

Login:
User submits email + password
→ Fetch user by email
→ Verify password with bcrypt
→ Generate JWT tokens
→ Return tokens + user info

Protected Route Access:
Client sends request with Bearer token
→ Extract token from Authorization header
→ Verify JWT signature and expiration
→ Extract user_id from token
→ Fetch user from database
→ Inject user into route handler
```

## API Endpoints

### POST /api/auth/register
Register a new user account.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "SecurePass123"
}
```

**Password Requirements:**
- Minimum 8 characters
- At least one letter
- At least one digit

**Response (201 Created):**
```json
{
  "access_token": "eyJhbGc...",
  "refresh_token": "eyJhbGc...",
  "token_type": "bearer",
  "user": {
    "id": "uuid-here",
    "email": "user@example.com",
    "is_active": true,
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-15T10:30:00Z"
  }
}
```

**Errors:**
- 400: Email already registered
- 422: Validation error (weak password, invalid email)

### POST /api/auth/login
Login to existing account.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "SecurePass123"
}
```

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGc...",
  "refresh_token": "eyJhbGc...",
  "token_type": "bearer",
  "user": {
    "id": "uuid-here",
    "email": "user@example.com",
    "is_active": true,
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-15T10:30:00Z"
  }
}
```

**Errors:**
- 401: Invalid credentials
- 403: Account inactive

### POST /api/auth/refresh
Refresh access token using refresh token.

**Request:**
```json
{
  "refresh_token": "eyJhbGc..."
}
```

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGc...",
  "token_type": "bearer"
}
```

**Errors:**
- 401: Invalid or expired refresh token

### GET /api/auth/me
Get current authenticated user information.

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response (200 OK):**
```json
{
  "id": "uuid-here",
  "email": "user@example.com",
  "is_active": true,
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

**Errors:**
- 401: Invalid or expired token
- 403: Account inactive

### POST /api/auth/logout
Logout (client-side token deletion).

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response (200 OK):**
```json
{
  "message": "Successfully logged out"
}
```

**Note:** JWT tokens are stateless. Actual logout is handled client-side by deleting tokens.

## Token Details

### Access Token
- **Expiration**: 30 minutes (configurable via `ACCESS_TOKEN_EXPIRE_MINUTES`)
- **Purpose**: Accessing protected API endpoints
- **Payload**:
  ```json
  {
    "user_id": "uuid",
    "exp": 1705318200,
    "type": "access"
  }
  ```

### Refresh Token
- **Expiration**: 7 days (configurable via `REFRESH_TOKEN_EXPIRE_DAYS`)
- **Purpose**: Getting new access tokens without re-login
- **Payload**:
  ```json
  {
    "user_id": "uuid",
    "exp": 1705923000,
    "type": "refresh"
  }
  ```

## Using Authentication in Code

### Protecting Routes

```python
from fastapi import APIRouter, Depends
from app.security.dependencies import get_current_user
from app.models.user import User

router = APIRouter()

@router.get("/protected")
async def protected_route(current_user: User = Depends(get_current_user)):
    """This route requires authentication."""
    return {"message": f"Hello {current_user.email}!"}
```

### Optional Authentication

```python
from typing import Optional

@router.get("/optional-auth")
async def optional_auth_route(current_user: Optional[User] = Depends(get_current_user)):
    """This route works with or without authentication."""
    if current_user:
        return {"message": f"Hello {current_user.email}!"}
    else:
        return {"message": "Hello guest!"}
```

### Password Utilities

```python
from app.security.password import hash_password, verify_password

# Hash password
password_hash, salt = hash_password("SecurePass123")

# Verify password
is_valid = verify_password("SecurePass123", password_hash)
```

### JWT Utilities

```python
from app.security.jwt import (
    create_access_token,
    create_refresh_token,
    verify_token,
    get_user_id_from_token
)

# Create tokens
access_token = create_access_token(user_id)
refresh_token = create_refresh_token(user_id)

# Verify token
payload = verify_token(token)

# Extract user_id
user_id = get_user_id_from_token(token)
```

### Encryption Utilities

```python
from app.security.encryption import encrypt_credentials, decrypt_credentials

# Encrypt
credentials = {"access_token": "abc123", "refresh_token": "xyz789"}
encrypted = encrypt_credentials(credentials)

# Decrypt
original = decrypt_credentials(encrypted)
```

## Client-Side Integration

### React/TypeScript Example

```typescript
// api/auth.ts
import axios from 'axios';

const API_URL = 'http://localhost:8000/api/auth';

export const authApi = {
  register: async (email: string, password: string) => {
    const response = await axios.post(`${API_URL}/register`, {
      email,
      password,
    });
    return response.data;
  },

  login: async (email: string, password: string) => {
    const response = await axios.post(`${API_URL}/login`, {
      email,
      password,
    });
    // Store tokens in localStorage or secure cookie
    localStorage.setItem('access_token', response.data.access_token);
    localStorage.setItem('refresh_token', response.data.refresh_token);
    return response.data;
  },

  logout: async () => {
    const token = localStorage.getItem('access_token');
    await axios.post(`${API_URL}/logout`, null, {
      headers: { Authorization: `Bearer ${token}` },
    });
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
  },

  getCurrentUser: async () => {
    const token = localStorage.getItem('access_token');
    const response = await axios.get(`${API_URL}/me`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    return response.data;
  },

  refreshToken: async () => {
    const refreshToken = localStorage.getItem('refresh_token');
    const response = await axios.post(`${API_URL}/refresh`, {
      refresh_token: refreshToken,
    });
    localStorage.setItem('access_token', response.data.access_token);
    return response.data.access_token;
  },
};

// Axios interceptor for automatic token refresh
axios.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      try {
        const newToken = await authApi.refreshToken();
        error.config.headers.Authorization = `Bearer ${newToken}`;
        return axios.request(error.config);
      } catch {
        // Refresh failed, redirect to login
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);
```

## Testing

### Manual Testing with curl

```bash
# Register
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"Test1234"}'

# Login
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"Test1234"}'

# Get current user (replace TOKEN with actual token)
curl -X GET http://localhost:8000/api/auth/me \
  -H "Authorization: Bearer TOKEN"

# Refresh token
curl -X POST http://localhost:8000/api/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token":"REFRESH_TOKEN"}'
```

### Automated Testing Script

```bash
# Run the test script
docker-compose exec backend python scripts/test_auth.py
```

Or from your local machine:
```bash
cd backend
python scripts/test_auth.py
```

## Security Best Practices

1. **Password Storage**: Never store plaintext passwords. Always use bcrypt hashing.

2. **Token Storage** (Client-side):
   - **Best**: Secure, httpOnly cookies
   - **Good**: localStorage with XSS protection
   - **Avoid**: Regular cookies without httpOnly flag

3. **HTTPS**: Always use HTTPS in production to prevent token interception.

4. **Token Expiration**: Short-lived access tokens (30 min) reduce risk if compromised.

5. **Refresh Tokens**: Store securely, rotate on use if possible.

6. **Rate Limiting**: Implement rate limiting on auth endpoints (Phase 2).

7. **Password Requirements**: Enforce strong passwords (8+ chars, mixed case, numbers).

## Environment Configuration

Required environment variables:

```bash
# JWT Configuration
JWT_SECRET_KEY=your-secret-key-here  # Generate with: openssl rand -hex 32
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Encryption (for mailbox credentials)
ENCRYPTION_KEY=your-fernet-key-here  # Generate with Python script
```

## Troubleshooting

### "Invalid credentials" on login
- Check password is correct
- Verify user exists in database
- Check logs for specific error

### "Token expired" errors
- Access tokens expire after 30 minutes
- Use refresh token to get new access token
- Re-login if refresh token also expired

### "Could not validate credentials"
- Token might be malformed
- JWT_SECRET_KEY might have changed
- Token signature verification failed

### Import errors in auth.py
- Ensure all dependencies installed: `pip install -r requirements.txt`
- Check Python path includes app directory
- Verify all __init__.py files exist

## Next Steps

After authentication is working:

1. **Frontend Integration**: Create login/register forms
2. **Email Provider**: Implement mailbox connection (requires auth)
3. **Subscriptions**: CRUD endpoints (require auth)
4. **User Settings**: Custom preferences (require auth)

---

**Authentication System Complete!** 🔐

All endpoints documented in the interactive API docs: http://localhost:8000/docs
