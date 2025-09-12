# Authentication Flow with AWS Cognito

## Overview

This document describes the authentication system implementation using AWS Cognito User Pool with FastAPI. The system supports user registration, email verification, login, token refresh, and logout functionality.

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Frontend      │    │   FastAPI API    │    │  AWS Cognito    │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                        │                       │
         │  HTTP Requests         │   boto3 SDK calls     │
         ├───────────────────────▶│──────────────────────▶│
         │                         │                       │
         │◀───────────────────────│◀──────────────────────│
         │  JWT Tokens             │   User Data/Tokens    │
```

## Authentication Flows

### 1. User Registration Flow

```
┌─────────┐    ┌──────────┐    ┌─────────────┐    ┌─────────────┐    ┌──────────────┐
│  User   │    │ Frontend │    │ FastAPI API │    │AWS Cognito  │    │Email Service │
└────┬────┘    └─────┬────┘    └──────┬──────┘    └──────┬──────┘    └──────┬───────┘
     │               │                │                  │                  │
     │ 1. Enter      │                │                  │                  │
     │ email &       │                │                  │                  │
     │ password      │                │                  │                  │
     │─────────────▶│                │                  │                  │
     │               │                │                  │                  │
     │               │ 2. Validate    │                  │                  │
     │               │ password       │                  │                  │
     │               │ strength       │                  │                  │
     │               │ (client-side)  │                  │                  │
     │               │                │                  │                  │
     │               │ 3. POST        │                  │                  │
     │               │ /api/auth/     │                  │                  │
     │               │ signup         │                  │                  │
     │               │ {email,        │                  │                  │
     │               │  password}     │                  │                  │
     │               │───────────────▶│                  │                  │
     │               │                │                  │                  │
     │               │                │ 4. Validate &    │                  │
     │               │                │ sanitize input   │                  │
     │               │                │ - Clean email    │                  │
     │               │                │ - Check password │                  │
     │               │                │ policy           │                  │
     │               │                │                  │                  │
     │               │                │ 5. sign_up()     │                  │
     │               │                │ - Username:email │                  │
     │               │                │ - Password       │                  │
     │               │                │ - SECRET_HASH    │                  │
     │               │                │ - UserAttributes │                  │
     │               │                │─────────────────▶│                  │
     │               │                │                  │                  │
     │               │                │                  │ 6. Send          │
     │               │                │                  │ verification     │
     │               │                │                  │ email with       │
     │               │                │                  │ 6-digit code     │
     │               │                │                  │─────────────────▶│
     │               │                │                  │                  │
     │               │                │ 7. Return        │                  │
     │               │                │ {UserSub,        │                  │
     │               │                │  UserConfirmed:  │                  │
     │               │                │  false}          │                  │
     │               │                │◀─────────────────│                  │
     │               │                │                  │                  │
     │               │ 8. Return      │                  │                  │
     │               │ SignUpResponse │                  │                  │
     │               │ {message,      │                  │                  │
     │               │  user_sub,     │                  │                  │
     │               │  email_verif.  │                  │                  │
     │               │  required:true}│                  │                  │
     │               │◀───────────────│                  │                  │
     │               │                │                  │                  │
     │ 9. Show       │                │                  │                  │
     │ "Check your   │                │                  │                  │
     │ email for     │                │                  │                  │
     │ confirmation" │                │                  │                  │
     │◀───────────── │                │                  │                  │
     │               │                │                  │                  │
     │     Wait for email...          │                  │                  │
     │   User receives 6-digit code   │                  │                  │
     │               │                │                  │                  │
     │ 10. Enter     │                │                  │                  │
     │ verification  │                │                  │                  │
     │ code: 123456  │                │                  │                  │
     │──────────────▶│                │                  │                  │
     │               │                │                  │                  │
     │               │ 11. POST       │                  │                  │
     │               │ /api/auth/     │                  │                  │
     │               │ confirm        │                  │                  │
     │               │ {email,        │                  │                  │
     │               │  confirmation_ │                  │                  │
     │               │  code}         │                  │                  │
     │               │───────────────▶│                  │                  │
     │               │                │                  │                  │
     │               │                │ 12. confirm_     │                  │
     │               │                │ sign_up()        │                  │
     │               │                │ - Username       │                  │
     │               │                │ - Code           │                  │
     │               │                │ - SECRET_HASH    │                  │
     │               │                │─────────────────▶│                  │
     │               │                │                  │                  │
     │               │                │ 13. User         │                  │
     │               │                │ confirmed        │                  │
     │               │                │ successfully     │                  │
     │               │                │◀─────────────────│                  │
     │               │                │                  │                  │
     │               │ 14. Return     │                  │                  │
     │               │ {message:      │                  │                  │
     │               │  "confirmed",  │                  │                  │
     │               │  confirmed:    │                  │                  │
     │               │  true}         │                  │                  │
     │               │◀───────────────│                  │                  │
     │               │                │                  │                  │
     │ 15. Show      │                │                  │                  │
     │ "Registration │                │                  │                  │
     │ complete!     │                │                  │                  │
     │ You can now   │                │                  │                  │
     │ login"        │                │                  │                  │
     │◀──────────────│                │                  │                  │
     │               │                │                  │                  │
```

### 2. User Login Flow

```
User      Frontend    FastAPI API    AWS Cognito    Token Store
  |           |            |             |               |
  |  Enter    |            |             |               |
  |  email &  |            |             |               |
  |  password |            |             |               |
  |---------->|            |             |               |
  |           | POST       |             |               |
  |           | /login     |             |               |
  |           |----------->|             |               |
  |           |            | Sanitize    |               |
  |           |            | email       |               |
  |           |            |------------>|               |
  |           |            |             |               |
  |           |            | initiate_   |               |
  |           |            | auth() +    |               |
  |           |            | SECRET_HASH |               |
  |           |            |------------>|               |
  |           |            | Return      |               |
  |           |            | tokens      |               |
  |           |            | (Access,    |               |
  |           |            | ID, Refresh)|               |
  |           |            |<------------|               |
  |           |            | Extract     |               |
  |           |            | user_sub    |               |
  |           |            | from ID     |               |
  |           |            | token       |               |
  |           |            |------------>|               |
  |           |            |             |               |
  |           |            | Store       |               |
  |           |            | refresh_    |               |
  |           |            | token →     |               |
  |           |            | username    |               |
  |           |            |---------------------------->|
  |           | Return     |             |               |
  |           | LoginResp  |             |               |
  |           | with tokens|             |               |
  |           |<-----------|             |               |
  |           | Store      |             |               |
  |           | tokens in  |             |               |
  |           | secure     |             |               |
  |           | storage    |             |               |
  | Redirect  |            |             |               |
  | to        |            |             |               |
  | dashboard |            |             |               |
  |<----------|            |             |               |
```

### 3. Token Refresh Flow

```
Frontend    FastAPI API    Token Store    AWS Cognito
    |           |               |             |
    | Access    |               |             |
    | token     |               |             |
    | expires   |               |             |
    |---------->|               |             |
    |           |               |             |
    | POST      |               |             |
    | /refresh- |               |             |
    | token     |               |             |
    |---------->|               |             |
    |           | Lookup        |             |
    |           | username for  |             |
    |           | refresh token |             |
    |           |-------------->|             |
    |           | Return stored |             |
    |           | username      |             |
    |           |<--------------|             |
    |           |               |             |
    |           | initiate_auth |             |
    |           | (REFRESH_     |             |
    |           | TOKEN_AUTH) + |             |
    |           | SECRET_HASH   |             |
    |           |---------------------------->|
    |           | Return new    |             |
    |           | Access &      |             |
    |           | ID tokens     |             |
    |           |<----------------------------|
    | Return    |               |             |
    | RefreshToken              |             |
    | Response  |               |             |
    |<----------|               |             |
    | Update    |               |             |
    | stored    |               |             |
    | tokens    |               |             |
```

### 4. Logout Flow

#### Client-Side Logout
```
User      Frontend    FastAPI API
  |           |            |
  | Click     |            |
  | logout    |            |
  |---------->|            |
  |           | POST       |
  |           | /logout    |
  |           |----------->|
  |           | Return     |
  |           | success    |
  |           | message    |
  |           |<-----------|
  |           | Delete all |
  |           | stored     |
  |           | tokens     |
  | Redirect  |            |
  | to login  |            |
  | page      |            |
  |<----------|            |
```

#### Global Logout (Server-Side)
```
User      Frontend    FastAPI API    AWS Cognito
  |           |            |             |
  | Click     |            |             |
  | "logout   |            |             |
  | all       |            |             |
  | devices"  |            |             |
  |---------->|            |             |
  |           | POST       |             |
  |           | /logout-   |             |
  |           | global     |             |
  |           | (with      |             |
  |           | access     |             |
  |           | token)     |             |
  |           |----------->|             |
  |           |            | Validate    |
  |           |            | access      |
  |           |            | token       |
  |           |            |------------>|
  |           |            |             |
  |           |            | global_     |
  |           |            | sign_out    |
  |           |            |(AccessToken)|
  |           |            |------------>|
  |           |            |             | Invalidate
  |           |            |             | all user
  |           |            |             | tokens
  |           |            |             |---------->
  |           |            | Success     |
  |           |            | response    |
  |           |            |<------------|
  |           | Return     |             |
  |           | success    |             |
  |           | message    |             |
  |           |<-----------|             |
  |           | Delete     |             |
  |           | local      |             |
  |           | tokens     |             |
  | Redirect  |            |             |
  | to login  |            |             |
  | page      |            |             |
  |<----------|            |             |
```

## API Endpoints

### Authentication Endpoints

| Endpoint | Method | Description | Request Body | Response |
|----------|--------|-------------|--------------|----------|
| `/api/auth/signup` | POST | Register new user | `{email, password}` | `{message, user_sub, email_verification_required}` |
| `/api/auth/confirm` | POST | Confirm email verification | `{email, confirmation_code}` | `{message, confirmed}` |
| `/api/auth/resend-confirmation` | POST | Resend verification code | `{email}` | `{message}` |
| `/api/auth/login` | POST | Authenticate user | `{email, password}` | `{access_token, id_token, refresh_token, expires_in, user_sub, email}` |
| `/api/auth/refresh-token` | POST | Refresh access token | `{refresh_token}` | `{access_token, id_token, expires_in}` |
| `/api/auth/logout` | POST | Client-side logout | - | `{message}` |
| `/api/auth/logout-global` | POST | Server-side logout | Headers: `Authorization: Bearer <token>` | `{message}` |

### Utility Endpoints

| Endpoint | Method | Description | Response |
|----------|--------|-------------|----------|
| `/api/auth/health` | GET | Service health check | `{status, service, version}` |
| `/api/auth/debug` | GET | Debug information | `{message, available_endpoints}` |
| `/api/auth/password-policy` | GET | Password requirements | `{policy, message}` |

## Password Policy

The system enforces the following password requirements:
- Minimum 8 characters
- At least one uppercase letter (A-Z)
- At least one lowercase letter (a-z)
- At least one digit (0-9)
- At least one special character (!@#$%^&*(),.?":{}|<>_)

## Token Management

### Token Types

1. **Access Token** (JWT)
   - Expires: 1 hour (default)
   - Used for API authorization
   - Contains user permissions and claims

2. **ID Token** (JWT)
   - Expires: 1 hour (default)
   - Contains user profile information
   - Used to extract user_sub

3. **Refresh Token**
   - Expires: 30 days (default)
   - Used to obtain new access/ID tokens
   - Stored with username mapping for SECRET_HASH

### Token Storage Strategy

**Frontend (Recommended):**
- Store tokens in `httpOnly` cookies (most secure)
- Alternative: Secure localStorage with XSS protection
- Never store in regular localStorage without encryption

**Backend:**
- In-memory mapping of refresh tokens to usernames
- For production: Consider Redis or database storage

## Security Considerations

### SECRET_HASH Implementation
- Required for Cognito App Clients with client secret
- Calculated as: `HMAC_SHA256(username + client_id, client_secret)`
- Stored username mapping enables refresh token functionality

### Input Sanitization
- Email addresses are sanitized (trimmed, lowercased)
- Control characters removed from inputs
- Validation happens at Pydantic model level

### Privacy & Logging
- Email addresses are hashed in logs: `user_1234`
- No sensitive data (passwords, tokens) logged
- Structured logging with appropriate log levels

### Error Handling
- Generic error messages to prevent enumeration attacks
- Specific errors only for validation (client-side feedback)
- Rate limiting through Cognito built-in protections

## Error Codes

| HTTP Status | Error Type | Description |
|-------------|------------|-------------|
| 400 | Bad Request | User not confirmed, invalid confirmation code |
| 401 | Unauthorized | Invalid credentials, expired/invalid token |
| 404 | Not Found | User not found |
| 409 | Conflict | User already exists |
| 422 | Validation Error | Invalid email format, weak password |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Cognito service errors, unexpected errors |

## Configuration

### Environment Variables

```bash
# Required
AWS_REGION=us-east-1
COGNITO_USER_POOL_ID=us-east-1_xxxxxxxxx
COGNITO_CLIENT_ID=xxxxxxxxxxxxxxxxxx

# Optional (for confidential clients)
COGNITO_CLIENT_SECRET=xxxxxxxxxxxxxxxxxx

# JWT Configuration
JWT_ALGORITHM=RS256
```

### AWS Cognito Configuration

**User Pool Settings:**
- Attributes: `email` (required, used as username)
- Policies: Password complexity as per requirements
- MFA: Optional (recommended for production)

**App Client Settings:**
- Auth flows: `ALLOW_USER_PASSWORD_AUTH`, `ALLOW_REFRESH_TOKEN_AUTH`
- Generate client secret: Yes (for server-side apps)
- Token expiration: Access (1h), Refresh (30d)


