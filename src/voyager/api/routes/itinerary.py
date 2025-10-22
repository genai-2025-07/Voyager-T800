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
from src.voyager.agents.runner import stream_response, get_session_state, save_session_state, clear_session_state, GenerationCancelledException, SESSION_MEMORY_TTL_SECONDS
from src.voyager.data.dynamodb import SessionMetadata
from langchain_core.messages import AIMessage, HumanMessage
from src.voyager.services.image.processor import resize_image_for_agent
from src.voyager.agents.cancellation_manager import get_cancellation_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix='/itinerary', tags=['itinerary'])


class ItineraryGenerateRequest(BaseModel):
    """Request model for itinerary generation with storage."""

    query: str
    session_id: str | None = None
    user_id: str | None = None
    include_events: bool | None = None
    use_weather: bool | None = None


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


@router.api_route('/generate/stream', methods=['GET','POST'])
async def generate_itinerary_stream_with_image(
    query: str = Query(...),
    session_id: str | None = Query(None),
    user_id: str | None = Query(None),
    image: UploadFile | None = File(None),
    http_request: Request = ...
):
    """
    Stream itinerary generation with optional image upload and cancellation support.
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
            image_bytes = await image.read()
            resized_bytes, media_type = resize_image_for_agent(image_bytes, image.content_type)
            image_base64 = base64.b64encode(resized_bytes).decode('utf-8')
            image_media_type = media_type
            
            thumbnail_metadata = image_storage_manager.upload_thumbnail(
                image_bytes=image_bytes,
                user_id=user_id,
                session_id=session_id,
                original_filename=image.filename,
                mime_type=image.content_type or 'image/jpeg'
            )
            logger.info(f'Thumbnail uploaded to S3: {thumbnail_metadata["s3_key"]}')
        
        # Restore session history from DynamoDB if needed (authenticated users only)
        agent_state = get_session_state(session_id)
        if not agent_state and user_id != 'anonymous':
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
        
        if thumbnail_metadata:
            user_message_entry['image_metadata'] = thumbnail_metadata
            user_message_entry['s3_key'] = thumbnail_metadata['s3_key']
        
        async def generate_stream():
            """Inner generator function for streaming response with cancellation."""
            itinerary_content = ''
            message_id = str(uuid.uuid4())
            was_cancelled = False
            
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
                
            except GenerationCancelledException as e:
                logger.info(f'Generation cancelled: {e}')
                was_cancelled = True
                # Send cancellation message
                yield f"data: {json.dumps({'cancelled': True, 'done': True, 'message': 'Generation stopped by user'})}\n\n"
                
            except Exception as e:
                logger.error(f'Streaming error: {e}', exc_info=True)
                yield f"data: {json.dumps({'error': str(e), 'done': True})}\n\n"
                return
            
            # Only save to DynamoDB if generation completed successfully (authenticated users only)
            if not was_cancelled and itinerary_content:
                try:
                    # For authenticated users, save to DynamoDB
                    if user_id != 'anonymous':
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
                    else:
                        logger.info(f'Anonymous session {session_id} - conversation kept in memory only (TTL: {SESSION_MEMORY_TTL_SECONDS}s)')
                    
                    # Send final message with metadata
                    yield f"data: {json.dumps({'chunk': '', 'done': True, 'itinerary_id': message_id, 'session_id': session_id})}\n\n"
                    
                except Exception as e:
                    logger.error(f'Failed to save to DynamoDB: {e}', exc_info=True)
                    yield f"data: {json.dumps({'error': 'Failed to save session', 'done': True})}\n\n"
        
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


@router.post('/generate/stop')
async def stop_generation(
    session_id: str = Query(...),
    user_id: str | None = Query(None)
):
    """
    Stop ongoing generation for a session.
    
    This endpoint allows the frontend to cancel an ongoing streaming operation.
    The cancellation is graceful and will stop after the current chunk is sent.
    """
    try:
        logger.info(f'Stopping generation for session: {session_id}')
        
        cancellation_mgr = get_cancellation_manager()
        was_running = cancellation_mgr.cancel(session_id)
        
        return {
            'success': True,
            'session_id': session_id,
            'message': 'Generation stop requested' if was_running else 'No active generation found'
        }
        
    except Exception as e:
        logger.error(f'Failed to stop generation: {str(e)}')
        raise HTTPException(status_code=500, detail='Failed to stop generation')

@router.post('/sessions', response_model=SessionCreateResponse)
async def create_session(request: SessionCreateRequest, http_request: Request):
    """
    Create a new session.
    
    For authenticated users: Session is persisted to DynamoDB.
    For anonymous users: Session exists in-memory only (TTL-based expiration).
    """
    try:
        user_id = request.user_id or 'anonymous'
        logger.info(f'Creating new session for user: {user_id}')

        # Generate unique session ID
        session_id = f'voyager_session_{uuid.uuid4().hex}'
        now = datetime.now(UTC).isoformat()

        # Create welcome message
        welcome_message = {
            'message_id': str(uuid.uuid4()),
            'sender': 'assistant',
            'timestamp': now,
            'content': "Welcome to Voyager-T800! I'm your intelligent AI travel assistant. Tell me about your dream trip - where would you like to go, when, and what kind of experience are you looking for?",
            'metadata': {'message_type': 'welcome', 'generated': True},
        }

        # For authenticated users, store in DynamoDB
        if user_id != 'anonymous':
            dynamodb_client = http_request.app.state.dynamodb_client
            
            session_metadata = SessionMetadata(
                user_id=user_id,
                session_id=session_id,
                session_summary='Session',
                started_at=now,
                messages=[welcome_message],
            )

            status_code = dynamodb_client.put_item(session_metadata)

            if status_code != 200:
                logger.error(f'Failed to store session in DynamoDB. Status code: {status_code}')
                raise HTTPException(status_code=500, detail='Failed to create session. Please try again.')
        else:
            # For anonymous users, just initialize in-memory session
            logger.info(f'Anonymous session {session_id} created (in-memory only, TTL: {SESSION_MEMORY_TTL_SECONDS}s)')

        return SessionCreateResponse(session_id=session_id, user_id=user_id, session_summary='Session', started_at=now)

    except Exception as e:
        logger.error(f'Failed to create session: {str(e)}')
        raise HTTPException(status_code=500, detail='Failed to create session. Please try again.')


@router.get('/sessions', response_model=SessionsListResponse)
async def list_sessions(user_id: str = Query('anonymous'), http_request: Request = ...):
    """
    List all sessions for a given user_id.
    
    For authenticated users: Returns sessions from DynamoDB.
    For anonymous users: Returns empty list (sessions are in-memory only and not persistent).
    """
    try:
        # Anonymous users don't have persistent sessions
        if user_id == 'anonymous':
            logger.info('Anonymous user - returning empty session list (sessions are in-memory only)')
            return SessionsListResponse(user_id=user_id, sessions=[])
        
        # For authenticated users, fetch from DynamoDB
        dynamodb_client = http_request.app.state.dynamodb_client  # type: ignore[attr-defined]
        items = dynamodb_client.list_sessions(user_id)
        return SessionsListResponse(user_id=user_id, sessions=items)
    except Exception as e:
        logger.error(f'Failed to list sessions: {str(e)}')
        raise HTTPException(status_code=500, detail='Failed to list sessions. Please try again.')


@router.delete('/sessions/{session_id}', response_model=SessionDeleteResponse)
async def delete_session(session_id: str, user_id: str = Query('anonymous'), http_request: Request = ...):
    """
    Delete a specific session for a user and remove associated images from S3.
    
    For authenticated users: Deletes from DynamoDB and removes S3 images.
    For anonymous users: Clears in-memory session only.
    """
    try:
        # For anonymous users, just clear in-memory session
        if user_id == 'anonymous':
            was_cleared = clear_session_state(session_id)
            if was_cleared:
                logger.info(f'Cleared anonymous session {session_id} from memory')
                return SessionDeleteResponse(session_id=session_id, user_id=user_id, deleted=True)
            else:
                # Session not found in memory - this is fine for anonymous sessions (may have expired)
                logger.info(f'Anonymous session {session_id} not found in memory (may have expired)')
                return SessionDeleteResponse(session_id=session_id, user_id=user_id, deleted=True)
        
        # For authenticated users, delete from DynamoDB and S3
        dynamodb_client = http_request.app.state.dynamodb_client
        image_storage_manager = http_request.app.state.image_storage_manager

        # Retrieve session first so we can find any associated images
        session_data = dynamodb_client.get_item(user_id, session_id)
        if session_data is None:
            raise HTTPException(status_code=404, detail='Session not found')

        # Collect S3 keys from messages (support top-level 's3_key' and nested 'image_metadata.s3_key')
        messages = session_data.get('messages', [])
        s3_keys = set()
        for msg in messages:
            # top-level s3_key
            key = msg.get('s3_key')
            if key:
                s3_keys.add(key)
            # nested image_metadata.s3_key
            image_metadata = msg.get('image_metadata') or {}
            nested_key = image_metadata.get('s3_key')
            if nested_key:
                s3_keys.add(nested_key)

        # Attempt to delete each image (log but don't fail the whole operation on individual image delete errors)
        failed_deletions = []
        for key in s3_keys:
            try:
                deleted = image_storage_manager.delete_image(key)
                if not deleted:
                    failed_deletions.append(key)
                    logger.warning("Failed to delete image for key '%s' (delete_image returned False).", key)
            except Exception:
                failed_deletions.append(key)
                logger.exception("Exception while deleting image with key '%s'.", key)

        if failed_deletions:
            logger.warning("Some image deletions failed for session %s: %s", session_id, failed_deletions)

        # Now delete the session from DynamoDB
        status_code = dynamodb_client.delete_item(user_id, session_id)
        if status_code == 404:
            # Race: session got removed after we fetched it
            raise HTTPException(status_code=404, detail='Session not found')
        if status_code != 200:
            raise HTTPException(status_code=500, detail='Failed to delete session')

        logger.info("Deleted session %s for user %s (images attempted: %d, failed: %d)",
                    session_id, user_id, len(s3_keys), len(failed_deletions))

        return SessionDeleteResponse(session_id=session_id, user_id=user_id, deleted=True)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Failed to delete session {session_id} for user {user_id}: {e}', exc_info=True)
        raise HTTPException(status_code=500, detail='Failed to delete session due to internal error')



@router.get('/{session_id}', response_model=ItineraryRetrieveResponse)
async def get_session_data(session_id: str, user_id: str = 'anonymous', http_request: Request = ...):
    """
    Retrieve session data with enriched image URLs.
    
    For authenticated users: Retrieves from DynamoDB.
    For anonymous users: Retrieves from in-memory session state (if available).
    """
    try:
        logger.info(f'Retrieving session data for session_id: {session_id}, user_id: {user_id}')
        
        # For anonymous users, try to retrieve from memory
        if user_id == 'anonymous':
            in_memory_messages = get_session_state(session_id)
            
            # If no in-memory session exists, return 404
            if not in_memory_messages:
                logger.info(f'Anonymous session {session_id} not found in memory (may have expired)')
                raise HTTPException(status_code=404, detail='Session not found or expired.')
            
            # Convert in-memory messages to API format
            formatted_messages = []
            for msg in in_memory_messages:
                if isinstance(msg, HumanMessage):
                    formatted_messages.append({
                        'sender': 'user',
                        'content': msg.content if isinstance(msg.content, str) else str(msg.content),
                        'timestamp': datetime.now(UTC).isoformat(),
                    })
                elif isinstance(msg, AIMessage):
                    formatted_messages.append({
                        'sender': 'assistant',
                        'content': msg.content if isinstance(msg.content, str) else str(msg.content),
                        'timestamp': datetime.now(UTC).isoformat(),
                    })
            
            return ItineraryRetrieveResponse(
                user_id='anonymous',
                session_id=session_id,
                session_summary='Anonymous Session',
                started_at=datetime.now(UTC).isoformat(),
                messages=formatted_messages,
                structured_itinerary=None,
            )
        
        # For authenticated users, retrieve from DynamoDB
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