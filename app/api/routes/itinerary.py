"""
Itinerary generation endpoints using LangGraph agent.
"""

import logging
import uuid
import json
import base64

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from fastapi import File, UploadFile
from app.agents.agent_runner import full_response, stream_response, get_session_state, save_session_state
from app.data_layer.dynamodb_client import SessionMetadata
from langchain_core.messages import AIMessage, HumanMessage


logger = logging.getLogger(__name__)
router = APIRouter(prefix='/itinerary', tags=['itinerary'])


class ItineraryGenerateRequest(BaseModel):
    """Request model for itinerary generation with storage."""

    query: str
    session_id: str | None = None
    user_id: str | None = None
    include_events: bool | None = None
    use_weather: bool | None = None

class ItineraryGenerateWithImageRequest(BaseModel):
    """Request model for itinerary generation with optional image."""
    query: str
    session_id: str | None = None
    user_id: str | None = None
    include_events: bool | None = None
    use_weather: bool | None = None

class ItineraryGenerateResponse(BaseModel):
    """Response model for generated itinerary with storage."""

    itinerary_id: str
    itinerary: str
    session_id: str
    structured_itinerary: dict | None = None
    success: bool = True


class ItineraryRetrieveResponse(BaseModel):
    """Response model for retrieved session data."""

    user_id: str
    session_id: str
    session_summary: str
    started_at: str
    messages: list[dict]
    structured_itinerary: dict | None = None


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


@router.post('/generate/stream-with-image')
async def generate_itinerary_stream_with_image(
    query: str = Query(...),
    session_id: str | None = Query(None),
    user_id: str | None = Query(None),
    image: UploadFile | None = File(None),
    http_request: Request = ...
):
    """
    Stream itinerary generation with optional image upload.
    Handles image resizing, thumbnail storage, and DynamoDB updates.
    """
    if not query:
        raise HTTPException(status_code=422, detail='Query is required.')
    
    try:
        logger.info(f'Starting streaming itinerary generation for query: {query[:100]}...')
        
        # Prepare session data
        user_id = user_id or 'anonymous'
        session_id = session_id or f'voyager_session_{uuid.uuid4().hex}'
        now = datetime.now(UTC).isoformat()
        
        # Get clients from app state
        dynamodb_client = http_request.app.state.dynamodb_client
        image_storage_manager = http_request.app.state.image_storage_manager
        
        # Process image if provided
        image_base64 = None
        image_media_type = None
        thumbnail_metadata = None
        
        if image:
            # Read image bytes
            image_bytes = await image.read()
            
            # Resize for agent (standardized size, e.g., 1024x1024 max)
            from app.services.image.image_processor import resize_image_for_agent
            resized_bytes, media_type = resize_image_for_agent(image_bytes, image.content_type)
            
            # Convert to base64 for agent
            image_base64 = base64.b64encode(resized_bytes).decode('utf-8')
            image_media_type = media_type
            
            # Upload thumbnail to S3
            thumbnail_metadata = image_storage_manager.upload_thumbnail(
                image_bytes=image_bytes,
                user_id=user_id,
                session_id=session_id,
                original_filename=image.filename,
                mime_type=image.content_type or 'image/jpeg'
            )
            logger.info(f'Thumbnail uploaded to S3: {thumbnail_metadata["s3_key"]}')
        
        # Restore session history from DynamoDB if needed
        agent_state = get_session_state(session_id)
        if not agent_state:
            existing_session = dynamodb_client.get_item(user_id, session_id)
            if existing_session and existing_session.get('messages'):
                restored_messages = []
                for msg in existing_session['messages']:
                    if msg.get('sender') == 'user':
                        restored_messages.append(HumanMessage(content=msg['content']))
                    elif msg.get('sender') == 'assistant':
                        restored_messages.append(AIMessage(content=msg['content']))
                
                if restored_messages:
                    save_session_state(session_id, restored_messages)
                    logger.info(f'Restored {len(restored_messages)} messages from DynamoDB for session {session_id}')
        
        # Create user message entry with image metadata
        user_message_entry = {
            'message_id': str(uuid.uuid4()),
            'sender': 'user',
            'timestamp': datetime.now(UTC).isoformat(),
            'content': query,
            'metadata': {
                'message_type': 'user_query',
                'has_image': image is not None,
            },
        }
        
        # Add thumbnail metadata to message if image was uploaded
        if thumbnail_metadata:
            user_message_entry['image_metadata'] = thumbnail_metadata
            user_message_entry['s3_key'] = thumbnail_metadata['s3_key']
        
        async def generate_stream():
            """Inner generator function for streaming response."""
            itinerary_content = ''
            message_id = str(uuid.uuid4())
            
            try:
                # Stream the agent's response
                for chunk in stream_response(
                    user_input=query,
                    session_id=session_id,
                    image_base64=image_base64,
                    image_media_type=image_media_type
                ):
                    itinerary_content += chunk
                    yield f"data: {json.dumps({'chunk': chunk, 'done': False})}\n\n"
                
                logger.info(f'Streaming complete. Total length: {len(itinerary_content)} chars')
                
                # Create assistant message entry
                itinerary_message = {
                    'message_id': message_id,
                    'sender': 'assistant',
                    'timestamp': now,
                    'content': itinerary_content,
                    'query': query,
                    'metadata': {'message_type': 'itinerary', 'generated': True},
                }
                
                # Update or create session in DynamoDB
                existing_session = dynamodb_client.get_item(user_id, session_id)
                if existing_session:
                    messages = existing_session.get('messages', [])
                    messages.append(user_message_entry)
                    messages.append(itinerary_message)
                    session_summary = existing_session.get('session_summary', '')
                    session_metadata = SessionMetadata(
                        user_id=user_id,
                        session_id=session_id,
                        session_summary=session_summary,
                        started_at=existing_session.get('started_at', now),
                        messages=messages,
                    )
                else:
                    session_summary = 'New Session'
                    session_metadata = SessionMetadata(
                        user_id=user_id,
                        session_id=session_id,
                        session_summary=session_summary,
                        started_at=now,
                        messages=[user_message_entry, itinerary_message],
                    )
                
                # Store in DynamoDB
                status_code = dynamodb_client.put_item(session_metadata)
                if status_code != 200:
                    logger.error(f'Failed to store session in DynamoDB. Status code: {status_code}')
                
                # Send final message with metadata
                yield f"data: {json.dumps({'chunk': '', 'done': True, 'itinerary_id': message_id, 'session_id': session_id})}\n\n"
            except Exception as e:
                logger.error(f'Streaming error: {e}', exc_info=True)
                yield f"data: {json.dumps({'error': str(e), 'done': True})}\n\n"
        
        return StreamingResponse(
            generate_stream(),
            media_type='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'X-Accel-Buffering': 'no',
            }
        )
    except Exception as e:
        logger.error(f'Failed to initialize streaming: {str(e)}')
        raise HTTPException(status_code=500, detail='Failed to start itinerary stream.')


@router.post('/generate/stream')
async def generate_itinerary_stream(request: ItineraryGenerateRequest, http_request: Request):
    """
    Stream itinerary generation token-by-token using LangGraph's message streaming.
    
    This endpoint provides real-time streaming of the agent's response as it's being generated.
    Uses Server-Sent Events (SSE) format for browser compatibility.
    """
    if not request.query:
        raise HTTPException(status_code=422, detail='Query is required.')

    try:
        logger.info(f'Starting streaming itinerary generation for query: {request.query[:100]}...')

        # Prepare session data
        user_id = request.user_id or 'anonymous'
        session_id = request.session_id or f'voyager_session_{uuid.uuid4().hex}'
        now = datetime.now(UTC).isoformat()

        # Get DynamoDB client from app state
        dynamodb_client = http_request.app.state.dynamodb_client

        # Restore session history from DynamoDB if needed
        agent_state = get_session_state(session_id)
        if not agent_state:  # Agent state is empty
            existing_session = dynamodb_client.get_item(user_id, session_id)
            if existing_session and existing_session.get('messages'):
                # Convert DynamoDB messages to LangChain messages for agent
                restored_messages = []
                for msg in existing_session['messages']:
                    if msg.get('sender') == 'user':
                        restored_messages.append(HumanMessage(content=msg['content']))
                    elif msg.get('sender') == 'assistant':
                        restored_messages.append(AIMessage(content=msg['content']))
                
                if restored_messages:
                    save_session_state(session_id, restored_messages)
                    logger.info(f'Restored {len(restored_messages)} messages from DynamoDB for session {session_id}')

        # Create a message entry for the USER query (for DynamoDB storage)
        user_message_entry = {
            'message_id': str(uuid.uuid4()),
            'sender': 'user',
            'timestamp': datetime.now(UTC).isoformat(),
            'content': request.query,
            'metadata': {
                'message_type': 'user_query',
            },
        }

        async def generate_stream():
            """Inner generator function for streaming response."""
            itinerary_content = ''
            message_id = str(uuid.uuid4())
            
            try:
                # Stream the agent's response using the LangGraph streaming
                for chunk in stream_response(
                    user_input=request.query,
                    session_id=session_id,
                ):
                    itinerary_content += chunk
                    # Send chunk as Server-Sent Event
                    yield f"data: {json.dumps({'chunk': chunk, 'done': False})}\n\n"
                
                logger.info(f'Streaming complete. Total length: {len(itinerary_content)} chars')
                

                # Create a message entry for the generated itinerary
                itinerary_message = {
                    'message_id': message_id,
                    'sender': 'assistant',
                    'timestamp': now,
                    'content': itinerary_content,
                    'query': request.query,
                    'metadata': {'message_type': 'itinerary', 'generated': True},
                }

                # Get existing session or create new one
                existing_session = dynamodb_client.get_item(user_id, session_id)

                if existing_session:
                    messages = existing_session.get('messages', [])
                    messages.append(user_message_entry)
                    messages.append(itinerary_message)
                    session_summary = existing_session.get('session_summary', '')

                    session_metadata = SessionMetadata(
                        user_id=user_id,
                        session_id=session_id,
                        session_summary=session_summary,
                        started_at=existing_session.get('started_at', now),
                        messages=messages,
                    )
                else:
                    session_summary = 'New Session'
                    session_metadata = SessionMetadata(
                        user_id=user_id,
                        session_id=session_id,
                        session_summary=session_summary,
                        started_at=now,
                        messages=[user_message_entry, itinerary_message],
                    )

                # Store in DynamoDB
                status_code = dynamodb_client.put_item(session_metadata)
                if status_code != 200:
                    logger.error(f'Failed to store session in DynamoDB. Status code: {status_code}')

                # Send final message with metadata
                yield f"data: {json.dumps({'chunk': '', 'done': True, 'itinerary_id': message_id, 'session_id': session_id})}\n\n"

            except Exception as e:
                logger.error(f'Streaming error: {e}', exc_info=True)
                yield f"data: {json.dumps({'error': str(e), 'done': True})}\n\n"

        return StreamingResponse(
            generate_stream(),
            media_type='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'X-Accel-Buffering': 'no',
            }
        )

    except Exception as e:
        logger.error(f'Failed to initialize streaming: {str(e)}')
        raise HTTPException(status_code=500, detail='Failed to start itinerary stream.')

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
    """Retrieve session data with enriched image URLs."""
    try:
        logger.info(f'Retrieving session data for session_id: {session_id}')
        
        dynamodb_client = http_request.app.state.dynamodb_client
        image_storage_manager = http_request.app.state.image_storage_manager
        
        session_data = dynamodb_client.get_item(user_id, session_id)
        if session_data is None:
            raise HTTPException(status_code=404, detail='Session not found.')
        
        # Enrich messages with pre-signed URLs for thumbnails
        messages = session_data.get('messages', [])
        enriched_messages = image_storage_manager.enrich_history_with_urls(messages)
        
        return ItineraryRetrieveResponse(
            user_id=session_data.get('user_id', ''),
            session_id=session_data.get('session_id', ''),
            session_summary=session_data.get('session_summary', ''),
            started_at=session_data.get('started_at', ''),
            messages=enriched_messages,
            structured_itinerary=session_data.get('structured_itinerary'),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Failed to retrieve session data: {str(e)}')
        raise HTTPException(status_code=500, detail='Failed to retrieve session data. Please try again.')