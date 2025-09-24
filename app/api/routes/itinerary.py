"""
Itinerary generation endpoints using RAG pipeline.
"""

import logging
import uuid

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from app.chains.itinerary_chain import full_response, initialize_retriever
from app.data_layer.dynamodb_client import SessionMetadata


logger = logging.getLogger(__name__)
router = APIRouter(prefix='/itinerary', tags=['itinerary'])


class ItineraryGenerateRequest(BaseModel):
    """Request model for itinerary generation with storage."""

    query: str
    session_id: str | None = None
    user_id: str | None = None


class ItineraryGenerateResponse(BaseModel):
    """Response model for generated itinerary with storage."""

    itinerary_id: str
    itinerary: str
    session_id: str
    success: bool = True


class ItineraryRetrieveResponse(BaseModel):
    """Response model for retrieved session data."""

    user_id: str
    session_id: str
    session_summary: str
    started_at: str
    messages: list[dict]


class SessionCreateRequest(BaseModel):
    """Request model for creating a new session."""

    user_id: str | None = None


class SessionCreateResponse(BaseModel):
    """Response model for created session."""

    session_id: str
    user_id: str
    session_summary: str
    started_at: str
    success: bool = True


class SessionsListResponse(BaseModel):
    """Response model for listing sessions for a user."""

    user_id: str
    sessions: list[dict]


class SessionDeleteResponse(BaseModel):
    """Response for session deletion."""

    session_id: str
    user_id: str
    deleted: bool = True


@router.post('/generate', response_model=ItineraryGenerateResponse)
async def generate_itinerary(request: ItineraryGenerateRequest, http_request: Request):
    """Generate an itinerary and store it in DynamoDB using SessionMetadata."""
    if not request.query:
        raise HTTPException(status_code=422, detail="Query is required.")

    try:
        logger.info(f'Generating and storing itinerary for query: {request.query[:100]}...')

        # Prepare session data
        user_id = request.user_id or 'anonymous'
        session_id = request.session_id or f'voyager_session_{uuid.uuid4().hex}'
        now = datetime.now(UTC).isoformat()

        # Get DynamoDB client from app state
        dynamodb_client = http_request.app.state.dynamodb_client

        # Initialize retriever with Weaviate client from app state
        weaviate_db_manager = http_request.app.state.weaviate_db_manager
        if weaviate_db_manager:
            initialize_retriever(weaviate_db_manager)
        else:
            logger.warning('Weaviate database manager not available in app state')

        # Create a message entry for the USER query
        user_message = {
            'message_id': str(uuid.uuid4()),
            'sender': 'user',
            'timestamp': datetime.now(UTC).isoformat(),
            'content': request.query,
            'metadata': {'message_type': 'user_query'},
        }

        # Generate itinerary using the existing chain
        itinerary_content = full_response(request.query, request.session_id or 'default_session')

        # Create a message entry for the generated itinerary
        itinerary_message = {
            'message_id': str(uuid.uuid4()),
            'sender': 'assistant',
            'timestamp': now,
            'content': itinerary_content,
            'query': request.query,
            'metadata': {'message_type': 'itinerary', 'generated': True},
        }

        # Try to get existing session data
        existing_session = dynamodb_client.get_item(user_id, session_id)

        if existing_session:
            # Update existing session
            messages = existing_session.get('messages', [])
            messages.append(user_message)
            messages.append(itinerary_message)

            session_metadata = SessionMetadata(
                user_id=user_id,
                session_id=session_id,
                session_summary=existing_session.get('session_summary', ''),
                started_at=existing_session.get('started_at', now),
                messages=messages,
            )
        else:
            # Create new session
            session_metadata = SessionMetadata(
                user_id=user_id,
                session_id=session_id,
                session_summary=f'Travel planning session for: {request.query[:50]}...',
                started_at=now,
                messages=[user_message, itinerary_message],
            )

        # Store in DynamoDB
        status_code = dynamodb_client.put_item(session_metadata)

        if status_code != 200:
            logger.error(f'Failed to store session in DynamoDB. Status code: {status_code}')
            raise HTTPException(status_code=500, detail='Failed to store itinerary. Please try again.')

        return ItineraryGenerateResponse(
            itinerary_id=itinerary_message['message_id'], itinerary=itinerary_content, session_id=session_id
        )

    except Exception as e:
        logger.error(f'Failed to generate and store itinerary: {str(e)}')
        raise HTTPException(status_code=500, detail='Failed to generate and store itinerary. Please try again.')


@router.post('/sessions', response_model=SessionCreateResponse)
async def create_session(request: SessionCreateRequest, http_request: Request):
    """Create a new session."""
    try:
        logger.info(f'Creating new session for user: {request.user_id or "anonymous"}')

        # Get DynamoDB client from app state
        dynamodb_client = http_request.app.state.dynamodb_client

        # Generate unique session ID
        session_id = f'voyager_session_{uuid.uuid4().hex}'
        user_id = request.user_id or 'anonymous'
        now = datetime.now(UTC).isoformat()

        # Create welcome message
        welcome_message = {
            'message_id': str(uuid.uuid4()),
            'sender': 'assistant',
            'timestamp': now,
            'content': "🚀 Welcome to Voyager-T800! I'm your intelligent AI travel assistant. Tell me about your dream trip - where would you like to go, when, and what kind of experience are you looking for?",
            'metadata': {'message_type': 'welcome', 'generated': True},
        }

        # Create session metadata
        session_metadata = SessionMetadata(
            user_id=user_id,
            session_id=session_id,
            session_summary='Session',
            started_at=now,
            messages=[welcome_message],
        )

        # Store in DynamoDB
        status_code = dynamodb_client.put_item(session_metadata)

        if status_code != 200:
            logger.error(f'Failed to store session in DynamoDB. Status code: {status_code}')
            raise HTTPException(status_code=500, detail='Failed to create session. Please try again.')

        return SessionCreateResponse(session_id=session_id, user_id=user_id, session_summary='Session', started_at=now)

    except Exception as e:
        logger.error(f'Failed to create session: {str(e)}')
        raise HTTPException(status_code=500, detail='Failed to create session. Please try again.')


@router.get('/sessions', response_model=SessionsListResponse)
async def list_sessions(user_id: str = Query('anonymous'), http_request: Request = ...):
    """List all sessions for a given user_id."""
    try:
        dynamodb_client = http_request.app.state.dynamodb_client  # type: ignore[attr-defined]
        items = dynamodb_client.list_sessions(user_id)
        # Do not refactor message structure; return as-is
        return SessionsListResponse(user_id=user_id, sessions=items)
    except Exception as e:
        logger.error(f'Failed to list sessions: {str(e)}')
        raise HTTPException(status_code=500, detail='Failed to list sessions. Please try again.')


@router.delete('/sessions/{session_id}', response_model=SessionDeleteResponse)
async def delete_session(session_id: str, user_id: str = Query('anonymous'), http_request: Request = ...):
    """Delete a specific session for a user."""
    try:
        dynamodb_client = http_request.app.state.dynamodb_client
        status_code = dynamodb_client.delete_item(user_id, session_id)
        if status_code == 404:
            raise HTTPException(status_code=404, detail='Session not found')
        if status_code != 200:
            raise HTTPException(status_code=500, detail='Failed to delete session')
        return SessionDeleteResponse(session_id=session_id, user_id=user_id, deleted=True)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Failed to delete session {session_id} for user {user_id}: {e}')
        raise HTTPException(status_code=500, detail='Failed to delete session due to internal error')


@router.get('/{session_id}', response_model=ItineraryRetrieveResponse)
async def get_session_data(session_id: str, user_id: str = 'anonymous', http_request: Request = ...):
    """Retrieve session data by session_id."""
    try:
        logger.info(f'Retrieving session data for session_id: {session_id}')

        # Get DynamoDB client from app state
        dynamodb_client = http_request.app.state.dynamodb_client

        # Get session data from DynamoDB
        session_data = dynamodb_client.get_item(user_id, session_id)

        if session_data is None:
            raise HTTPException(status_code=404, detail='Session not found.')

        return ItineraryRetrieveResponse(
            user_id=session_data.get('user_id', ''),
            session_id=session_data.get('session_id', ''),
            session_summary=session_data.get('session_summary', ''),
            started_at=session_data.get('started_at', ''),
            messages=session_data.get('messages', []),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Failed to retrieve session data: {str(e)}')
        raise HTTPException(status_code=500, detail='Failed to retrieve session data. Please try again.')
