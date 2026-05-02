# Authentication & Authorisation

> JWT-based access/refresh flow, bcrypt password storage, Fernet credential encryption, and multi-tenant isolation via `user_id` filters. Implemented under `backend/app/security/`.

## Overview

The authentication system provides secure user registration, login, and token-based authentication using industry-standard practices:

- **Password Security**: bcrypt hashing with automatic salt generation
- **Token Authentication**: JWT (JSON Web Tokens) with access and refresh tokens
- **Credential Encryption**: Fernet symmetric encryption for storing sensitive data (mailbox tokens)
- **FastAPI Integration**: Dependency injection for protecting routes

### Architecture

```
Security Layer
├── password.py             # bcrypt password hashing and verification
├── jwt.py                  # JWT token creation and verification
├── encryption.py           # Fernet credential encryption
├── two_factor.py           # TOTP / Email-OTP / backup codes facade
├── email_verification.py   # Email-verification token + rate limiter
├── events.py               # Security event logger (failed logins, …)
└── dependencies.py         # FastAPI authentication dependencies

API Layer
└── api/auth/               # Auth router package (Phase 7 split)
    ├── router.py           # Aggregate APIRouter (mounts the four sub-routers)
    ├── registration.py     # POST /register, /verify-email, /resend-verification
    ├── login.py            # POST /login, /refresh, /logout · GET /me
    ├── two_factor.py       # 6 routes under /2fa/*
    ├── account.py          # /me/profile, /me/password, /me/preferences,
    │                       # GET+PATCH /me/language, DELETE /me
    └── _email_dispatch.py  # Internal helper for verification + 2FA emails

Schemas
└── schemas/auth.py         # Pydantic models for validation

Models
└── models/user.py          # SQLAlchemy User model
```

### Security Flow

```
Registration (email-verified):
User submits email + password (+ optional invite_token)
→ Validate password strength (8+ chars, letter + digit)
→ Validate invite token if REQUIRE_INVITE_TOKEN
→ Hash password with bcrypt
→ Store user with email_verified=False
→ Send verification email with token
→ Return { message, email }   ← no tokens yet

Email verification:
User clicks verification link
→ Look up token, check expiry + brute-force lockout
→ Mark email_verified=True, clear token
→ Issue access + refresh JWTs (auto-login)
→ Return tokens + user info

Login (no 2FA):
User submits email + password
→ Brute-force gate (≥5 failed → 429 for 15 min)
→ Verify password with bcrypt
→ Reject if email not verified or account inactive
→ Issue access + refresh JWTs
→ Return tokens + user info

Login (2FA enabled):
User submits email + password
→ … same gates as above …
→ If 2FA = email: send OTP and return TwoFactorRequiredResponse(method=email)
→ If 2FA = TOTP: return TwoFactorRequiredResponse(method=totp)
→ Client calls POST /2fa/verify-login with email + code
→ TwoFactorAuth.verify_two_factor (TOTP / email-OTP / backup code)
→ Issue access + refresh JWTs

Protected Route Access:
Client sends request with Bearer token
→ Extract token from Authorization header
→ Verify JWT signature and expiration
→ Extract user_id from token
→ Fetch user from database
→ Inject user into route handler
```

## API Endpoints

The 19 endpoints below are mounted under the `/api/auth` prefix and split across four modules. The interactive OpenAPI schema at `http://localhost:8000/docs` is the source of truth for request/response shapes — the tables here summarise the contract.

| Method | Path                              | Auth | Module          | Purpose |
|--------|-----------------------------------|------|-----------------|---------|
| POST   | `/register`                       | —    | registration.py | Create unverified user, send verification email |
| POST   | `/verify-email`                   | —    | registration.py | Verify token, auto-login (returns tokens) |
| POST   | `/resend-verification`            | —    | registration.py | Resend verification email (rate-limited) |
| POST   | `/login`                          | —    | login.py        | Credentials + 2FA challenge dispatch |
| POST   | `/refresh`                        | —    | login.py        | Rotate access token from refresh token |
| GET    | `/me`                             | ✓    | login.py        | Current authenticated user |
| POST   | `/logout`                         | ✓    | login.py        | Log a logout event (JWT is stateless) |
| POST   | `/2fa/verify-login`               | —    | two_factor.py   | Complete login with 2FA code |
| POST   | `/2fa/setup`                      | ✓    | two_factor.py   | Start 2FA setup (TOTP or email) |
| POST   | `/2fa/enable`                     | ✓    | two_factor.py   | Confirm setup, enable 2FA, return backup codes |
| POST   | `/2fa/disable`                    | ✓    | two_factor.py   | Disable 2FA (password-confirmed) |
| GET    | `/2fa/status`                     | ✓    | two_factor.py   | Current 2FA status for user |
| POST   | `/2fa/backup-codes/regenerate`    | ✓    | two_factor.py   | Replace existing backup codes |
| PUT    | `/me/profile`                     | ✓    | account.py      | Update display_name and/or email |
| PUT    | `/me/password`                    | ✓    | account.py      | Change password (current password required) |
| PUT    | `/me/preferences`                 | ✓    | account.py      | Merge UI preferences into `User.settings` |
| GET    | `/me/language`                    | ✓    | account.py      | Read `User.preferred_language` |
| PATCH  | `/me/language`                    | ✓    | account.py      | Set `User.preferred_language` (or null) |
| DELETE | `/me`                             | ✓    | account.py      | Delete account (password + confirm flag) |

### Registration & email verification

#### POST /api/auth/register

Register a new user. The user is created with `email_verified=False` and a verification email is dispatched. **No tokens are issued at this stage** — the client must complete `/verify-email` first.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "SecurePass123",
  "display_name": "Optional",
  "invite_token": "optional-when-REQUIRE_INVITE_TOKEN"
}
```

**Password requirements:** ≥ 8 characters, at least one letter, at least one digit.

**Response (201 Created)** — `EmailVerificationResponse`:
```json
{
  "message": "Registration successful! Please check your email to verify your account.",
  "email": "user@example.com"
}
```

**Errors:**
- 400: Email already registered (or unverified account already exists), invalid/used/expired invite token
- 422: Validation error (weak password, invalid email)

#### POST /api/auth/verify-email

Consume a verification token and auto-login.

**Request:**
```json
{ "token": "<32+ char token from email>" }
```

**Response (200 OK)** — `TokenResponse` (access + refresh + user).

**Errors:** 400 (invalid/expired/used token) · 429 (IP brute-force lockout).

#### POST /api/auth/resend-verification

**Request:** `{ "email": "user@example.com" }` · **Response:** `EmailVerificationResponse`. Rate-limited to 12/hour per email; IP brute-force lockout applies. Returns a generic "if an account exists…" message when the email is unknown (no enumeration leak).

### Login, refresh, session

#### POST /api/auth/login

Verifies credentials and either issues tokens or returns a 2FA challenge.

**Request:** `{ "email": "...", "password": "..." }`

**Response (200 OK)** — depends on 2FA state:
- 2FA disabled → `TokenResponse` (access + refresh + user)
- 2FA enabled  → `TwoFactorRequiredResponse`:
  ```json
  { "requires_2fa": true, "method": "totp" | "email", "message": "..." }
  ```

**Errors:** 401 (invalid credentials) · 403 (email not verified, account inactive) · 429 (≥ 5 failed attempts in 15 min).

#### POST /api/auth/refresh

**Request:** `{ "refresh_token": "..." }` · **Response:** `{ "access_token": "...", "token_type": "bearer" }` · **Errors:** 401 (invalid token, wrong type, user not found/inactive).

#### GET /api/auth/me

Returns the current authenticated user (`UserResponse`). Errors: 401 (invalid/expired token) · 403 (account inactive).

#### POST /api/auth/logout

Logs a logout event. JWTs are stateless; actual logout is client-side token deletion. Response: `{ "message": "Successfully logged out" }`.

### Two-factor authentication

#### POST /api/auth/2fa/verify-login

Completes a login that returned `TwoFactorRequiredResponse`.

**Request:**
```json
{ "email": "user@example.com", "code": "123456", "is_backup_code": false }
```

**Response (200 OK):** `TokenResponse`. Errors: 400 (2FA not enabled), 401 (invalid code).

#### POST /api/auth/2fa/setup

**Auth required.** Body: `{ "method": "totp" | "email" }`. Returns:
- TOTP → `{ method: "totp", secret, qr_code, message }` (client must scan + call `/2fa/enable`).
- Email → sends OTP, returns `{ method: "email", message }`.

#### POST /api/auth/2fa/enable

**Auth required.** Confirms setup and stores backup codes.

**Request:**
```json
{ "method": "totp" | "email", "secret": "<TOTP secret, required for totp>", "verification_code": "123456" }
```

**Response:** `{ success, message, backup_codes: [...] }` (codes shown once).

#### POST /api/auth/2fa/disable

**Auth required.** Body: `{ "password": "..." }`. Returns `{ success, message }`. Errors: 400 (2FA not enabled), 401 (wrong password).

#### GET /api/auth/2fa/status

**Auth required.** Returns `{ enabled, method, backup_codes_remaining }`.

#### POST /api/auth/2fa/backup-codes/regenerate

**Auth required.** Replaces existing backup codes. Returns `{ success, message, backup_codes: [...] }`. Errors: 400 (2FA not enabled).

### Account management

#### PUT /api/auth/me/profile

**Auth required.** Body: `{ "display_name"?: "...", "email"?: "..." }`. Updating the email sets `email_verified=False`. Returns the updated `UserResponse`. Errors: 400 (new email already registered).

#### PUT /api/auth/me/password

**Auth required.** Body: `{ "current_password": "...", "new_password": "..." }`. Same strength rules as registration. Errors: 400 (wrong current password, weak new password).

#### PUT /api/auth/me/preferences

**Auth required.** Merges into `User.settings` JSONB. Body fields (all optional): `theme` (`light|dark|system`), `language` (`xx` or `xx-XX`), `currency` (3-letter ISO), `date_format`, `timezone`. Returns `{ message, preferences }`.

> **Note:** `language` written here lives in `settings.language`; the dedicated `/me/language` endpoints (below) target the first-class `User.preferred_language` column. The two are intentionally kept distinct — see `audits/` §C.2.

#### GET /api/auth/me/language

**Auth required.** Returns `{ preferred_language: "en" | "fr" | null, message }`.

#### PATCH /api/auth/me/language

**Auth required.** Body: `{ "language": "en" | "fr" | null }` (null = browser detection). Errors: 422 (unsupported code).

#### DELETE /api/auth/me

**Auth required.** Body: `{ "password": "...", "confirm": true }`. Cascading delete via SQLAlchemy `cascade="all, delete-orphan"` on the user's mailboxes, subscriptions, etc. Errors: 400 (wrong password, confirm not set).

## JWT Tokens

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

### Implementation

```python
# backend/app/security/jwt.py
from datetime import datetime, timedelta
import jwt
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

security = HTTPBearer()

def create_access_token(user_id: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "user_id": user_id,
        "exp": expire,
        "type": "access"
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def create_refresh_token(user_id: str) -> str:
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "user_id": user_id,
        "exp": expire,
        "type": "refresh"
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    try:
        payload = jwt.decode(
            credentials.credentials,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )
        return payload["user_id"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
```

## Password Storage

```python
# backend/app/security/password.py
import bcrypt

def hash_password(password: str) -> tuple[str, str]:
    """Hash password with bcrypt and return (hash, salt)"""
    salt = bcrypt.gensalt()
    password_hash = bcrypt.hashpw(password.encode('utf-8'), salt)
    return password_hash.decode('utf-8'), salt.decode('utf-8')

def verify_password(password: str, password_hash: str) -> bool:
    """Verify password against hash"""
    return bcrypt.checkpw(
        password.encode('utf-8'),
        password_hash.encode('utf-8')
    )
```

Passwords are never stored in plaintext. Salts are bcrypt-generated automatically per password.

## Mailbox Credential Encryption

Mailbox tokens (access + refresh) are stored Fernet-encrypted in `mailboxes.encrypted_credentials` (see data-model.md §3.2). The Fernet key is loaded from `ENCRYPTION_KEY`.

```python
# backend/app/security/encryption.py
from cryptography.fernet import Fernet
import os
import json

# Load encryption key from environment
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY").encode()
cipher = Fernet(ENCRYPTION_KEY)

def encrypt_credentials(credentials: dict) -> str:
    """Encrypt credentials dictionary to string"""
    json_str = json.dumps(credentials)
    encrypted = cipher.encrypt(json_str.encode())
    return encrypted.decode()

def decrypt_credentials(encrypted_credentials: str) -> dict:
    """Decrypt credentials string to dictionary"""
    decrypted = cipher.decrypt(encrypted_credentials.encode())
    return json.loads(decrypted.decode())

# Generate encryption key (run once, store in environment)
def generate_encryption_key() -> str:
    return Fernet.generate_key().decode()
```

Decryption happens only at the moment a provider call is being made (see email-pipeline.md). The decrypted dict is never logged.

## Multi-Tenancy Model

Tenant isolation is enforced at the application layer: every user-scoped query filters by `user_id`. There is no PostgreSQL row-level security in Phase 1; defense-in-depth via RLS is deferred to Phase 4. See `security.md` for the full rationale and broader application-level security model.

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

## Operational Notes

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

### Security Best Practices

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

### Environment Configuration

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

### Troubleshooting

**"Invalid credentials" on login**
- Check password is correct
- Verify user exists in database
- Check logs for specific error

**"Token expired" errors**
- Access tokens expire after 30 minutes
- Use refresh token to get new access token
- Re-login if refresh token also expired

**"Could not validate credentials"**
- Token might be malformed
- JWT_SECRET_KEY might have changed
- Token signature verification failed

**Import errors in app/api/auth/**
- Ensure all dependencies installed: `pip install -r requirements.txt`
- Check Python path includes app directory
- Verify all `__init__.py` files exist

### Next Steps

After authentication is working:

1. **Frontend Integration**: Create login/register forms
2. **Email Provider**: Implement mailbox connection (requires auth)
3. **Subscriptions**: CRUD endpoints (require auth)
4. **User Settings**: Custom preferences (require auth)

All endpoints documented in the interactive API docs: `http://localhost:8000/docs`.
