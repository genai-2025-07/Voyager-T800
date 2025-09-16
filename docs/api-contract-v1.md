# Voyager-T800 API Contract v1

This document describes the REST API endpoints for Voyager-T800's travel planning service.

## Base URL

- **Development**: `http://localhost:8000`
- **Production**: `http://localhost:8001`

## Authentication

Currently supports anonymous sessions. User authentication endpoints are available but not required for basic functionality.

## Response Format

All responses follow this structure:

```json
{
  "success": true,
  "data": { ... },
  "error": null,
  "request_id": "uuid-string"
}
```

Error responses:
```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "details": { ... }
  },
  "request_id": "uuid-string"
}
```

## Endpoints

### Itinerary Generation

#### POST `/api/v1/itinerary/generate`

Generate a travel itinerary based on user query.

**Request Body:**
```json
{
  "query": "Plan a 5-day trip to Japan",
  "session_id": "voyager_session_abc123",
  "user_id": "anonymous"
}
```

**Response (200):**
```json
{
  "itinerary_id": "msg_uuid_123",
  "itinerary": "# 5-Day Japan Itinerary\n\n## Day 1: Tokyo Arrival...",
  "session_id": "voyager_session_abc123",
  "success": true
}
```

**Response (500):**
```json
{
  "success": false,
  "error": {
    "code": "GENERATION_FAILED",
    "message": "Failed to generate itinerary. Please try again."
  }
}
```

### Session Management

#### POST `/api/v1/itinerary/sessions`

Create a new travel planning session.

**Request Body:**
```json
{
  "user_id": "anonymous"
}
```

**Response (200):**
```json
{
  "session_id": "voyager_session_abc123",
  "user_id": "anonymous",
  "session_summary": "Session",
  "started_at": "2024-01-15T10:30:00Z",
  "success": true
}
```

#### GET `/api/v1/itinerary/sessions`

List all sessions for a user.

**Query Parameters:**
- `user_id` (string, optional): User identifier (default: "anonymous")

**Response (200):**
```json
{
  "user_id": "anonymous",
  "sessions": [
    {
      "session_id": "voyager_session_abc123",
      "session_summary": "5-day Japan trip planning",
      "started_at": "2024-01-15T10:30:00Z",
      "messages": [...]
    }
  ]
}
```

#### GET `/api/v1/itinerary/{session_id}`

Retrieve a specific session with full message history.

**Path Parameters:**
- `session_id` (string): Session identifier

**Query Parameters:**
- `user_id` (string, optional): User identifier (default: "anonymous")

**Response (200):**
```json
{
  "user_id": "anonymous",
  "session_id": "voyager_session_abc123",
  "session_summary": "5-day Japan trip planning",
  "started_at": "2024-01-15T10:30:00Z",
  "messages": [
    {
      "message_id": "msg_123",
      "sender": "assistant",
      "timestamp": "2024-01-15T10:30:00Z",
      "content": "Welcome to Voyager-T800!...",
      "metadata": {"message_type": "welcome"}
    },
    {
      "message_id": "msg_124",
      "sender": "user",
      "timestamp": "2024-01-15T10:31:00Z",
      "content": "Plan a 5-day trip to Japan",
      "metadata": {"message_type": "user_query"}
    }
  ]
}
```

**Response (404):**
```json
{
  "success": false,
  "error": {
    "code": "SESSION_NOT_FOUND",
    "message": "Session not found."
  }
}
```

#### DELETE `/api/v1/itinerary/sessions/{session_id}`

Delete a specific session.

**Path Parameters:**
- `session_id` (string): Session identifier

**Query Parameters:**
- `user_id` (string, optional): User identifier (default: "anonymous")

**Response (200):**
```json
{
  "session_id": "voyager_session_abc123",
  "user_id": "anonymous",
  "deleted": true
}
```

#### POST `/api/v1/itinerary/sessions/transfer`

Transfer sessions from one user to another (useful for anonymous → authenticated user migration).

**Request Body:**
```json
{
  "from_user_id": "anonymous",
  "to_user_id": "user@example.com"
}
```

**Response (200):**
```json
{
  "migrated": 3
}
```

### Authentication (Optional)

#### POST `/api/auth/login`

Authenticate a user.

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "password123"
}
```

**Response (200):**
```json
{
  "access_token": "jwt_token_here",
  "user_sub": "user_uuid",
  "email": "user@example.com"
}
```

#### POST `/api/auth/signup`

Register a new user.

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "password123"
}
```

**Response (201):**
```json
{
  "message": "User created successfully. Please confirm your email."
}
```

## Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `GENERATION_FAILED` | 500 | Itinerary generation failed |
| `SESSION_NOT_FOUND` | 404 | Session does not exist |
| `INVALID_REQUEST` | 400 | Malformed request body |
| `AUTHENTICATION_FAILED` | 401 | Invalid credentials |
| `INTERNAL_ERROR` | 500 | Unexpected server error |

## Rate Limits

- **Itinerary Generation**: 10 requests per minute per user
- **Session Operations**: 100 requests per minute per user

## Data Models

### SessionMetadata
```json
{
  "user_id": "string",
  "session_id": "string", 
  "session_summary": "string",
  "started_at": "ISO 8601 timestamp",
  "messages": [
    {
      "message_id": "string",
      "sender": "user|assistant",
      "timestamp": "ISO 8601 timestamp",
      "content": "string",
      "metadata": {
        "message_type": "string",
        "generated": "boolean"
      }
    }
  ]
}
```

### Message
```json
{
  "message_id": "string",
  "sender": "user|assistant", 
  "timestamp": "ISO 8601 timestamp",
  "content": "string",
  "metadata": {
    "message_type": "user_query|itinerary|welcome",
    "generated": "boolean"
  }
}
```

## Examples

### Complete Flow

1. **Create Session**
```bash
curl -X POST http://localhost:8000/api/v1/itinerary/sessions \
  -H "Content-Type: application/json" \
  -d '{"user_id": "anonymous"}'
```

2. **Generate Itinerary**
```bash
curl -X POST http://localhost:8000/api/v1/itinerary/generate \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Plan a 3-day trip to Paris",
    "session_id": "voyager_session_abc123",
    "user_id": "anonymous"
  }'
```

3. **Retrieve Session**
```bash
curl http://localhost:8000/api/v1/itinerary/voyager_session_abc123?user_id=anonymous
```

## Changelog

### v1.0.0 (2024-01-15)
- Initial API release
- Session management
- Itinerary generation
- Basic authentication support
