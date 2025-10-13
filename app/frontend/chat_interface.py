import mimetypes
import os
import re
import uuid

from datetime import datetime

import requests
import streamlit as st

from PIL import Image, UnidentifiedImageError

from app.config.config import settings


# Configuration
API_BASE_URL = settings.api_base_url
STREAMLIT_ENV = settings.streamlit_env

WELCOME_MESSAGE = (
    "🚀 Welcome to Voyager-T800! I'm your intelligent AI travel assistant. "
    'Tell me about your dream trip - where would you like to go, when, and what kind of experience are you looking for?'
)

APP_PAGE_TITLE = settings.voyager_page_title
APP_PAGE_ICON = settings.voyager_page_icon
APP_PAGE_TAGLINE = settings.voyager_page_tagline

MAX_INPUT_LENGTH = settings.voyager_max_input_length
SESSIONS_PAGE_SIZE = settings.voyager_sessions_page_size
IMAGE_DISPLAY_WIDTH = settings.image_display_width

st.set_page_config(page_title=APP_PAGE_TITLE, page_icon=APP_PAGE_ICON, layout='wide')

MIN_LOADED_IMAGE_WIDTH = 200
MIN_LOADED_IMAGE_HEIGHT = 200


def load_styles():
    try:
        css_path = os.path.join(os.path.dirname(__file__), 'style.css')
        with open(css_path, encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        st.warning('Warning: style.css not found.')
        return ''
    except OSError as e:
        st.warning(f'Warning: Cannot read style.css: {e}. Using default styling.')
        return ''


css_styles = load_styles()

if css_styles:
    st.markdown(f'<style>{css_styles}</style>', unsafe_allow_html=True)

# Initialize session state
if 'messages' not in st.session_state:
    st.session_state.messages = []

if 'user_input' not in st.session_state:
    st.session_state.user_input = ''

if 'session_id' not in st.session_state:
    st.session_state.session_id = None

if 'user_id' not in st.session_state:
    st.session_state.user_id = f'anon_{uuid.uuid4().hex}'

# Simple holder for last derived weather summary block
if 'weather_summary' not in st.session_state:
    st.session_state.weather_summary = None

if 'sessions' not in st.session_state:
    st.session_state.sessions = {}

if 'current_session_id' not in st.session_state:
    st.session_state.current_session_id = None

if 'sessions_page' not in st.session_state:
    st.session_state.sessions_page = 1

if 'confirm_delete' not in st.session_state:
    st.session_state.confirm_delete = None

if 'auth' not in st.session_state:
    st.session_state.auth = None


def get_current_session_weather_state():
    """Get the weather toggle state for the current session."""
    current_session_id = st.session_state.get('current_session_id')
    if current_session_id is None:
        return True
    session_entry = st.session_state.sessions.get(current_session_id)
    if session_entry is None:
        # Initialize default weather flag for this session id in local cache
        st.session_state.sessions[current_session_id] = {
            'name': 'Trip Planning',
            'messages': [],
            'created': datetime.now(),
            'use_weather': True,
        }
        return True
    return bool(session_entry.get('use_weather', True))


# API communication functions
def call_api_endpoint(
    endpoint: str, data: dict | None = None, method: str = 'POST', params: dict | None = None
) -> dict | None:
    """Make API call to FastAPI backend using a unified helper.

    Args:
        endpoint: Path after /api/v1
        data: JSON body for POST/PUT/PATCH
        method: HTTP method ('GET', 'POST', 'DELETE', 'PUT', 'PATCH')
        params: Querystring parameters for GET/DELETE
    """
    try:
        url = f'{API_BASE_URL}/api/v1{endpoint}'
        method_upper = (method or 'POST').upper()
        timeout = settings.api_timeout

        if method_upper == 'GET':
            response = requests.get(url, params=params, timeout=timeout)
        elif method_upper == 'DELETE':
            response = requests.delete(url, params=params, timeout=timeout)
        elif method_upper == 'PUT':
            response = requests.put(url, json=data, timeout=timeout)
        elif method_upper == 'PATCH':
            response = requests.patch(url, json=data, timeout=timeout)
        else:
            response = requests.post(url, json=data, timeout=timeout)

        if response.status_code in (200, 201):
            return response.json()
        else:
            if STREAMLIT_ENV == 'dev':
                st.error(f'API Error: {response.status_code} - {response.text}')
            else:
                st.error('Request failed. Please try again.')
            return None

    except requests.exceptions.RequestException as e:
        st.error('Connection Error: Unable to connect to the API server. Please check if the backend is running.')
        if STREAMLIT_ENV == 'dev':
            st.error(f'Debug info: {str(e)}')
        return None


def call_auth_endpoint(
    endpoint: str, data: dict | None = None, method: str = 'POST', params: dict | None = None
) -> dict | None:
    """Call authentication endpoints on the FastAPI backend using a unified helper."""
    try:
        url = f'{API_BASE_URL}/api/auth{endpoint}'
        method_upper = (method or 'POST').upper()
        timeout = settings.api_timeout

        if method_upper == 'GET':
            response = requests.get(url, params=params, timeout=timeout)
        elif method_upper == 'DELETE':
            response = requests.delete(url, params=params, timeout=timeout)
        elif method_upper == 'PUT':
            response = requests.put(url, json=data, timeout=timeout)
        elif method_upper == 'PATCH':
            response = requests.patch(url, json=data, timeout=timeout)
        else:
            response = requests.post(url, json=data, timeout=timeout)
        if response.status_code in (200, 201):
            return response.json()
        else:
            if STREAMLIT_ENV == 'dev':
                st.error(f'API Error: {response.status_code} - {response.text}')
            else:
                st.error('Request failed. Please try again.')
            return None
    except requests.exceptions.RequestException as e:
        st.error('Unable to reach auth service.')
        if STREAMLIT_ENV == 'dev':
            st.error(f'Debug info: {str(e)}')
        return None
    except Exception as e:
        st.error(f'Unexpected Error: {str(e)}')
        return None


def login_user(email: str, password: str) -> dict | None:
    return call_auth_endpoint('/login', {'email': email, 'password': password}, method='POST')


def delete_session_api(user_id: str, session_id: str) -> bool:
    try:
        _ = call_api_endpoint(
            f'/itinerary/sessions/{session_id}',
            method='DELETE',
            params={'user_id': user_id},
        )
        # If no exception and helper didn't return None due to error, treat as success
        return True
    except Exception:
        return False


def list_sessions_api(user_id: str) -> list[dict]:
    try:
        data = call_api_endpoint('/itinerary/sessions', method='GET', params={'user_id': user_id})
        if isinstance(data, dict):
            return data.get('sessions', [])
        return []
    except Exception:
        return []


def signup_user(email: str, password: str) -> dict | None:
    return call_auth_endpoint('/signup', {'email': email, 'password': password}, method='POST')


def confirm_signup(email: str, code: str) -> dict | None:
    return call_auth_endpoint('/confirm', {'email': email, 'confirmation_code': code}, method='POST')


def resend_confirmation(email: str) -> dict | None:
    return call_auth_endpoint('/resend-confirmation', {'email': email}, method='POST')


def upload_image_to_backend(uploaded_file) -> dict | None:
    """Upload and validate an image using the FastAPI backend.
    
    Args:
        uploaded_file: Streamlit UploadedFile object
        
    Returns:
        dict: Image metadata if successful, None if failed
    """
    try:
        url = f'{API_BASE_URL}/api/v1/images/upload'
        
        # Reset file pointer to beginning
        uploaded_file.seek(0)
        
        # Prepare multipart form data
        files = {'file': (uploaded_file.name, uploaded_file, mimetypes.guess_type(uploaded_file.name)[0] or uploaded_file.type)}
        
        response = requests.post(url, files=files, timeout=settings.api_timeout)
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 400:
            # Validation error
            error_detail = response.json().get('detail', 'Image validation failed.')
            st.error(f'Image validation failed: {error_detail}')
            return None
        else:
            st.error('Failed to upload image. Please try again.')
            if STREAMLIT_ENV == 'dev':
                st.error(f'API Error: {response.status_code} - {response.text}')
            return None
            
    except requests.exceptions.RequestException as e:
        st.error('Connection Error: Unable to connect to the API server.')
        if STREAMLIT_ENV == 'dev':
            st.error(f'Debug info: {str(e)}')
        return None


def validate_image_client(uploaded_file) -> bool:
    """Quick client-side checks before sending to backend.

    Performs shallow validation to provide fast feedback and avoid
    unnecessary network calls for obviously invalid files.

    Checks:
    - Extension in ['jpg','jpeg','png','webp']
    - Size <= 3.75 MB (to match backend limit)
    - Resolution <= 4096 x 4096

    Returns:
        True if all checks pass, otherwise shows a UI message and returns False.
    """
    try:
        allowed_exts = {'jpg', 'jpeg', 'png', 'webp'}

        filename = getattr(uploaded_file, 'name', '') or ''
        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
        if ext not in allowed_exts:
            st.warning('Unsupported image file type. Allowed: jpg, jpeg, png, webp.')
            return False

        file_size = getattr(uploaded_file, 'size', None)
        if file_size is None:
            try:
                file_size = len(uploaded_file.getbuffer())  # type: ignore[attr-defined]
            except Exception:
                file_size = None

        if file_size is not None:
            max_bytes = int(settings.image_max_size_mb * 1024 * 1024)
            if file_size > max_bytes:
                st.warning('Image is too large. Maximum allowed size is {settings.image_max_size_mb} MB.')
                return False

        # Resolution check
        try:
            uploaded_file.seek(0)
            with Image.open(uploaded_file) as img:
                width, height = img.size
            if width > 4096 or height > 4096:
                st.warning('Image resolution exceeds 4096×4096 px.')
                return False
            # Minimal size UX check (keep existing behavior)
            if width < MIN_LOADED_IMAGE_WIDTH or height < MIN_LOADED_IMAGE_HEIGHT:
                st.warning(
                    f'Image is too small. Please, upload image of size at least '
                    f'{MIN_LOADED_IMAGE_WIDTH}x{MIN_LOADED_IMAGE_HEIGHT} px'
                )
                return False
        except UnidentifiedImageError:
            st.warning('Invalid image file.')
            return False
        finally:
            try:
                uploaded_file.seek(0)
            except Exception:
                pass

        return True

    except Exception:
        # Silent fallback to allow backend to provide definitive validation
        try:
            uploaded_file.seek(0)
        except Exception:
            pass
        return True
    except Exception as e:
        st.error(f'Unexpected error uploading image: {str(e)}')
        return None


def hydrate_sessions_from_backend(user_id: str) -> None:
    """Pick the most recent session from backend and load its messages; create if none."""
    try:
        cloud_sessions = list_sessions_api(user_id)
        latest_session_id = None
        latest_started_at = None
        for item in cloud_sessions:
            sid = item.get('session_id')
            started_at = item.get('started_at')
            try:
                started_dt = datetime.fromisoformat(str(started_at).replace('Z', '+00:00')) if started_at else None
            except Exception:
                started_dt = None
            if sid and (latest_started_at is None or (started_dt and started_dt > latest_started_at)):
                latest_started_at = started_dt
                latest_session_id = sid

        if latest_session_id:
            loaded = load_session_from_api(latest_session_id, user_id)
            if loaded:
                st.session_state.current_session_id = latest_session_id
                st.session_state.session_id = latest_session_id
                st.session_state.messages = loaded['messages'].copy()
                return

        created = create_new_session_api(user_id)
        if created:
            st.session_state.current_session_id = created['session_id']
            st.session_state.session_id = created['session_id']
            st.session_state.messages = [
                {
                    'role': 'assistant',
                    'content': WELCOME_MESSAGE,
                }
            ]
    except Exception as e:
        st.error(f'Failed to load sessions: {e}')


# def generate_itinerary(user_message: str, session_id: str, user_id: str = 'anonymous') -> dict | None:
#     """Generate itinerary and store it in DynamoDB using FastAPI backend."""
#     # Include feature flags from UI state
#     include_events_flag = bool(st.session_state.get('include_events', False))
#     use_weather_flag = bool(get_current_session_weather_state())
#     data = {
#         'query': user_message,
#         'session_id': session_id,
#         'user_id': user_id,
#         'include_events': include_events_flag,
#         'use_weather': use_weather_flag,
#     }
#     result = call_api_endpoint('/itinerary/generate', data, method='POST')
#     if result and 'itinerary' in result and 'itinerary_id' in result:
#         return result
#     return None


def stream_itinerary_response(user_message: str, session_id: str, user_id: str = 'anonymous'):
    """
    Stream itinerary generation from the backend token-by-token.
    
    This is a generator function compatible with st.write_stream() for real-time display.
    
    Args:
        user_message: User's query
        session_id: Current session ID
        user_id: Current user ID
        
    Yields:
        str: Response chunks as they arrive from the backend
        
    The function stores metadata (itinerary_id, session_id) in st.session_state
    for later retrieval.
    """
    import json
    
    try:
        # Include feature flags from UI state
        include_events_flag = bool(st.session_state.get('include_events', False))
        use_weather_flag = bool(get_current_session_weather_state())
        
        url = f'{API_BASE_URL}/api/v1/itinerary/generate/stream'
        data = {
            'query': user_message,
            'session_id': session_id,
            'user_id': user_id,
            'include_events': include_events_flag,
            'use_weather': use_weather_flag,
        }
        
        # Make streaming request with longer timeout for agent execution
        response = requests.post(url, json=data, stream=True, timeout=300)
        
        if response.status_code != 200:
            if STREAMLIT_ENV == 'dev':
                st.error(f'API Error: {response.status_code} - {response.text}')
            else:
                st.error('Request failed. Please try again.')
            return
        
        # Process Server-Sent Events stream
        for line in response.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                
                # Parse SSE format: "data: {...}"
                if line_str.startswith('data: '):
                    json_str = line_str[6:]  # Remove "data: " prefix
                    
                    try:
                        event_data = json.loads(json_str)
                        
                        # Check if streaming is complete
                        if event_data.get('done'):
                            # Store metadata in session state for later use
                            if 'itinerary_id' in event_data:
                                st.session_state.temp_itinerary_id = event_data['itinerary_id']
                            if 'session_id' in event_data:
                                st.session_state.temp_session_id = event_data['session_id']
                            if 'structured_itinerary' in event_data:
                                st.session_state.temp_structured_itinerary = event_data['structured_itinerary']
                            if 'error' in event_data:
                                st.error(f'Error during generation: {event_data["error"]}')
                            break
                        
                        # Yield chunk for display
                        chunk = event_data.get('chunk', '')
                        if chunk:
                            yield chunk
                            
                    except json.JSONDecodeError:
                        # Skip malformed JSON lines
                        continue
        
    except requests.exceptions.RequestException as e:
        st.error('Connection Error: Unable to connect to the API server.')
        if STREAMLIT_ENV == 'dev':
            st.error(f'Debug info: {str(e)}')
    except Exception as e:
        st.error(f'Unexpected Error: {str(e)}')
        if STREAMLIT_ENV == 'dev':
            st.error(f'Debug info: {str(e)}')


def get_session_data(session_id: str, user_id: str = 'anonymous') -> dict | None:
    """Retrieve session data by session_id using FastAPI backend."""
    try:
        data = call_api_endpoint(f'/itinerary/{session_id}', method='GET', params={'user_id': user_id})
        return data
    except Exception as e:
        if STREAMLIT_ENV == 'dev':
            st.error(f'Unexpected Error: {str(e)}')
        return None


def create_new_session_api(user_id: str = 'anonymous') -> dict | None:
    """Create a new session via API."""
    try:
        data = {'user_id': user_id}
        result = call_api_endpoint('/itinerary/sessions', data, method='POST')

        if result and 'session_id' in result:
            return {
                'session_id': result['session_id'],
                'user_id': result['user_id'],
                'session_summary': result['session_summary'],
                'created': datetime.fromisoformat(result['started_at'].replace('Z', '+00:00')),
            }
        return None

    except Exception as e:
        st.error(f'Failed to create new session: {str(e)}')
        return None


def load_session_from_api(session_id: str, user_id: str = 'anonymous') -> dict | None:
    """Load session data from API and convert to Streamlit format."""
    session_data = get_session_data(session_id, user_id)

    if not session_data:
        return None

    # Convert API session data to Streamlit message format
    messages = []
    for msg in session_data.get('messages', []):
        if msg.get('sender') == 'assistant':
            messages.append(
                {'role': 'assistant', 'content': msg.get('content', ''), 'itinerary_id': msg.get('message_id', '')}
            )
        elif msg.get('sender') == 'user':
            messages.append({'role': 'user', 'content': msg.get('content', '')})

    return {
        'session_id': session_data['session_id'],
        'messages': messages,
        'session_summary': session_data.get('session_summary', ''),
        'created': datetime.fromisoformat(session_data.get('started_at', '').replace('Z', '+00:00')),
    }


# Initialize or load current session
if st.session_state.session_id is None:
    # If authenticated, hydrate and DO NOT create automatically
    if st.session_state.auth is not None:
        hydrate_sessions_from_backend(st.session_state.user_id)
        # Leave as-is if none found; user can create explicitly
    else:
        # Anonymous users get an initial session
        session_data = create_new_session_api(st.session_state.user_id)
        if session_data:
            st.session_state.session_id = session_data['session_id']
            st.session_state.current_session_id = session_data['session_id']
            st.session_state.messages = [
                {
                    'role': 'assistant',
                    'content': WELCOME_MESSAGE,
                }
            ]
        else:
            st.error('Failed to initialize session. Please refresh the page.')
            st.stop()


def load_session(session_id: str):
    """Load a specific session from API"""
    # Load session data from API
    session_data = load_session_from_api(session_id, st.session_state.user_id)

    if not session_data:
        st.error(f"Session '{session_id}' not found or failed to load.")
        return

    # Update current session
    st.session_state.current_session_id = session_id
    st.session_state.session_id = session_id
    st.session_state.messages = session_data['messages'].copy()

    # Update local cache without renaming existing sessions
    existing_name = st.session_state.sessions.get(session_id, {}).get('name')
    stable_name = existing_name or session_data.get('session_summary') or 'Trip Planning'
    st.session_state.sessions[session_id] = {
        'name': stable_name,
        'messages': session_data['messages'].copy(),
        'created': session_data['created'],
    }


def create_new_session():
    """Create a new session via API"""
    # Create new session via API
    session_data = create_new_session_api(st.session_state.user_id)
    if session_data:
        st.session_state.current_session_id = session_data['session_id']
        st.session_state.session_id = session_data['session_id']
        st.session_state.messages = [
            {
                'role': 'assistant',
                'content': WELCOME_MESSAGE,
            }
        ]

        # Add to local sessions cache with a stable name
        existing_name = st.session_state.sessions.get(session_data['session_id'], {}).get('name')
        stable_name = existing_name or 'Trip Planning'
        st.session_state.sessions[session_data['session_id']] = {
            'name': stable_name,
            'messages': st.session_state.messages.copy(),
            'created': session_data['created'],
        }
    else:
        st.error('Failed to create new session. Please try again.')


def clear_chat():
    """Clear chat history"""
    st.session_state.messages = []
    st.session_state.messages.append({'role': 'assistant', 'content': WELCOME_MESSAGE, 'timestamp': datetime.now()})


def get_dynamic_chat_placeholder():
    """Return a context-aware placeholder for the chat input.

    - If no prior user message exists, encourage providing trip basics.
    - If a prior user message exists, suggest a follow-up with a short snippet.
    """
    try:
        messages = st.session_state.get('messages', [])
        last_user_message = None
        for msg in reversed(messages):
            if msg.get('role') == 'user' and isinstance(msg.get('content'), str):
                content = msg['content'].strip()
                if content:
                    last_user_message = content
                    break
        if not last_user_message:
            return 'Describe your trip: destination, dates, budget, interests…'
        fragment = re.sub(r'\s+', ' ', last_user_message)[:80]
        if len(last_user_message) > 80:
            fragment = fragment.rstrip() + '…'
        return f"Follow up on: '{fragment}' — or ask to adjust days, budget, or pace"
    except Exception:
        return 'Type your travel plans or questions…'


st.title(f'{APP_PAGE_ICON} {APP_PAGE_TITLE}')
st.markdown(APP_PAGE_TAGLINE)

with st.sidebar:
    st.header('👤 Account')
    if st.session_state.auth is None:
        with st.expander('Login', expanded=False):
            login_email = st.text_input('Email', key='login_email')
            login_password = st.text_input('Password', type='password', key='login_password')
            if st.button('Sign In', key='login_btn', use_container_width=True):
                auth_resp = login_user(login_email.strip(), login_password)
                if auth_resp and 'access_token' in auth_resp:
                    st.session_state.auth = auth_resp
                    st.session_state.user_id = auth_resp.get('user_sub') or auth_resp.get('email')

                    st.session_state.sessions = {}
                    st.session_state.current_session_id = None
                    st.session_state.session_id = None
                    st.session_state.messages = []
                    # Hydrate from backend; do NOT create automatically
                    hydrate_sessions_from_backend(st.session_state.user_id)
                    st.rerun()
        with st.expander('Sign Up', expanded=False):
            su_email = st.text_input('Email', key='su_email')
            su_password = st.text_input('Password', type='password', key='su_password')
            if st.button('Create Account', key='signup_btn', use_container_width=True):
                su_resp = signup_user(su_email.strip(), su_password)
                if su_resp:
                    st.success('Account created. Please confirm your email with the code sent to you.')
            st.caption('After receiving the code in your email, confirm below:')
            code = st.text_input('Confirmation Code', key='su_code')
            if st.button('Confirm Sign Up', key='confirm_signup_btn', use_container_width=True):
                c_resp = confirm_signup(su_email.strip(), code.strip())
                if c_resp:
                    st.success('Email confirmed. You can now log in.')
            if st.button('Resend Code', key='resend_code_btn', use_container_width=True):
                resend_confirmation(su_email.strip())
                st.info('If the email exists and is not confirmed, a new code was sent.')
    else:
        st.success('Logged in')
        if st.button('Sign Out', key='logout_btn', use_container_width=True):
            st.session_state.auth = None
            st.session_state.user_id = f'anon_{uuid.uuid4().hex}'
            st.session_state.sessions = {}
            st.session_state.session_id = None
            st.session_state.current_session_id = None
            st.session_state.messages = []
            st.rerun()

    st.markdown('---')
    st.header('💬 Sessions')

    if st.button('➕ New Session', type='primary', use_container_width=True):
        create_new_session()
        st.rerun()

    st.markdown('---')
    st.subheader('Tools')
    include_events = st.checkbox(
        'Include available events',
        value=st.session_state.get('include_events', False),
        help='Enrich itinerary with local events',
    )
    # Persist the toggle so main area can read it when sending requests
    st.session_state['include_events'] = include_events

    st.markdown('---')

    # Weather toggle in sidebar
    st.header('🌤️ Weather')
    use_weather = get_current_session_weather_state()
    new_use_weather = st.checkbox('Enable weather-aware recommendations', value=use_weather)

    # Update the session-specific weather toggle
    if st.session_state.current_session_id in st.session_state.sessions:
        st.session_state.sessions[st.session_state.current_session_id]['use_weather'] = new_use_weather

    st.markdown('---')

    # Render sessions fetched from backend
    sessions_list = list_sessions_api(st.session_state.user_id)
    if sessions_list:
        st.subheader('📚 Session History')

        # Sort by creation date (newest first)
        sessions_items = list(st.session_state.sessions.items())
        try:
            sessions_items.sort(
                key=lambda item: item[1].get('created', datetime.min),
                reverse=True,
            )
        except Exception:
            pass

        # Pagination
        total_sessions = len(sessions_list)
        page_size = max(1, SESSIONS_PAGE_SIZE)
        total_pages = max(1, (total_sessions + page_size - 1) // page_size)
        if st.session_state.sessions_page > total_pages:
            st.session_state.sessions_page = total_pages
        if st.session_state.sessions_page < 1:
            st.session_state.sessions_page = 1

        if total_pages > 1:
            pcols = st.columns([1, 3, 1])
            with pcols[0]:
                if st.button('◀', key='sessions_prev', help='Previous page'):
                    st.session_state.sessions_page = max(1, st.session_state.sessions_page - 1)
                    st.rerun()
            with pcols[1]:
                st.markdown(f'Page {st.session_state.sessions_page} / {total_pages}')
            with pcols[2]:
                if st.button('▶', key='sessions_next', help='Next page'):
                    st.session_state.sessions_page = min(total_pages, st.session_state.sessions_page + 1)
                    st.rerun()

        start_idx = (st.session_state.sessions_page - 1) * page_size
        end_idx = start_idx + page_size
        visible_sessions = sessions_list[start_idx:end_idx]

        for item in visible_sessions:
            session_id = item.get('session_id')
            session_name = item.get('session_summary') or 'Trip Planning'
            try:
                created_date = datetime.fromisoformat(str(item.get('started_at', '')).replace('Z', '+00:00')).strftime(
                    '%m/%d'
                )
            except Exception:
                created_date = ''

            with st.container():
                is_active = session_id == st.session_state.current_session_id

                if is_active:
                    st.markdown(
                        f"""
                        <div class = "session-card">
                            <div class ="session-name">
                                🟢 {session_name}
                            </div>
                            <div class="session-date">
                                Created: {created_date}
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                else:
                    if st.button(
                        f' {session_name}',
                        key=f'session_{session_id}',
                        help=f'Click to switch to {session_name}',
                        use_container_width=True,
                    ):
                        load_session(session_id)
                        st.rerun()

                    st.caption(f'Created: {created_date}')

                # Deletion flow uses backend-only persistence; UI deletes simply re-renders list
                if st.button('🗑️ Delete', key=f'delete_{session_id}', help=f'Delete {session_name}'):
                    st.session_state.confirm_delete = session_id
                if st.session_state.confirm_delete == session_id:
                    st.warning(f"Are you sure you want to delete '{session_name}'?")
                    if st.button('✅ Yes, delete', key=f'confirm_{session_id}'):
                        if delete_session_api(st.session_state.user_id, session_id):
                            # If we deleted the active session, clear selection
                            if st.session_state.current_session_id == session_id:
                                st.session_state.current_session_id = None
                                st.session_state.session_id = None
                                st.session_state.messages = []
                            st.session_state.confirm_delete = None
                            st.rerun()
                        else:
                            st.error('Failed to delete session. Please try again.')
                    if st.button('❌ Cancel', key=f'cancel_{session_id}'):
                        st.session_state.confirm_delete = None
                st.markdown('---')

    st.markdown('---')
    st.header('Chat Controls')
    if st.button('🗑️ Clear Chat', type='secondary', use_container_width=True):
        clear_chat()
        st.rerun()

    st.markdown('---')
    st.subheader('💡Tips')
    st.markdown("""
    Try asking:
    - "Plan a 5-day trip to Japan"
    - "I want a relaxing beach vacation"
    - "Make day 3 more adventurous"
    - "What's the best time to visit?"
    """)

    st.markdown('---')
    st.subheader('ℹ️ About')
    st.markdown(
        'Voyager-T800 uses your custom itinerary chain with Llama3-8B to create personalized travel itineraries.'
    )

# Main chat interface
chat_container = st.container()

with chat_container:
    for _i, message in enumerate(st.session_state.messages):
        if message['role'] == 'user':
            if 'image' in message and message['image'] is not None:
                st.image(message['image'], width=IMAGE_DISPLAY_WIDTH)
            else:
                st.markdown(
                    f"""
                    <div class="message-container">
                        <div class ="message-bubble">
                            {message['content']}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        else:
            st.markdown(
                f"""
                <div class="message-container-left">
                    <div class="message-bubble-left">
                        {message['content']}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

# Weather summary card
use_weather = get_current_session_weather_state()
if st.session_state.weather_summary and use_weather:
    ws = st.session_state.weather_summary
    with st.container():
        st.markdown('### 🌤️ Weather (summary)')
        st.caption(f'{ws.get("city", "")} | Units: {ws.get("units", "metric")}')
        for d in ws.get('days', [])[:5]:
            st.markdown(
                f'- {d["date"]}: {d["label"]} — {d["temp_min_c"]}–{d["temp_max_c"]}°C, precip {d["precipitation_mm"]}mm'
            )

st.markdown('---')

placeholder_text = get_dynamic_chat_placeholder()
user_input = st.chat_input(placeholder_text, accept_file=True, file_type=['jpg', 'jpeg', 'png', 'webp'])

if user_input:
    # Determine if this submit includes an image
    has_image = hasattr(user_input, 'files') and bool(user_input.files)
    image_valid = False

    if has_image:
        uploaded_file = user_input.files[0]

        # Quick client-side validation before calling backend
        if not validate_image_client(uploaded_file):
            image_valid = False
        else:
            with st.spinner('Validating image...'):
                # Send image to backend for validation
                validation_result = upload_image_to_backend(uploaded_file)

            if validation_result:
                image_id = validation_result.get('image_id')
                width = validation_result.get('width')
                height = validation_result.get('height')

                # Store image metadata for later use (in order to put image above text)
                st.session_state.temp_image_data = {
                    'image': uploaded_file,
                    'image_id': image_id,
                    'image_metadata': validation_result,
                }

                image_valid = True
            else:
                image_valid = False

    # Proceed with text generation if either no image or the image is valid
    if getattr(user_input, 'text', None) and (not has_image or image_valid):
        text_value = user_input.text.strip()
        if not text_value:
            st.warning('Your message is empty.')
        elif len(text_value) > MAX_INPUT_LENGTH:
            st.warning(f'Message too long (max {MAX_INPUT_LENGTH} characters).')
        else:
            # Display the user message immediately before streaming starts
            st.markdown(
                f"""
                <div class="message-container">
                    <div class ="message-bubble">
                        {text_value}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            
            # Display image if present
            if has_image and image_valid and hasattr(st.session_state, 'temp_image_data'):
                st.image(st.session_state.temp_image_data['image'], width=IMAGE_DISPLAY_WIDTH)
            
            # Add text message to session state
            st.session_state.messages.append({'role': 'user', 'content': text_value})
            
            # Add image message if we have one (after text, before itinerary)
            if has_image and image_valid and hasattr(st.session_state, 'temp_image_data'):
                st.session_state.messages.append({
                    'role': 'user',
                    'image': st.session_state.temp_image_data['image'],
                    'image_id': st.session_state.temp_image_data['image_id'],
                    'image_metadata': st.session_state.temp_image_data['image_metadata'],
                })
                # Clear temp data
                del st.session_state.temp_image_data
            
            # Stream the response token-by-token with custom styling
            # Create a placeholder for the streaming response
            response_container = st.empty()
            
            streamed_response = ''
            with response_container.container():
                st.markdown('<div class="message-container-left">', unsafe_allow_html=True)
                stream_placeholder = st.empty()
                
                # Stream and accumulate the response
                for chunk in stream_itinerary_response(
                    text_value,
                    st.session_state.session_id,
                    st.session_state.user_id
                ):
                    streamed_response += chunk
                    # Update the display with accumulated content using the same styling as chat history
                    stream_placeholder.markdown(
                        f'<div class="message-bubble-left">{streamed_response}</div>',
                        unsafe_allow_html=True
                    )
                
                st.markdown('</div>', unsafe_allow_html=True)
            
            # Save the streamed response to session state
            if streamed_response and streamed_response.strip():
                cleaned = streamed_response.strip().lower()
                if cleaned not in ['error', 'none', 'null']:
                    # Get the itinerary_id that was stored during streaming
                    itinerary_id = getattr(st.session_state, 'temp_itinerary_id', '')
                    
                    st.session_state.messages.append({
                        'role': 'assistant',
                        'content': streamed_response.strip(),
                        'itinerary_id': itinerary_id
                    })
                    
                    # Clean up temporary state
                    if hasattr(st.session_state, 'temp_itinerary_id'):
                        del st.session_state.temp_itinerary_id
                    if hasattr(st.session_state, 'temp_session_id'):
                        del st.session_state.temp_session_id
                    if hasattr(st.session_state, 'temp_structured_itinerary'):
                        del st.session_state.temp_structured_itinerary
                else:
                    st.warning('Assistant returned an error message, not saved.')
            else:
                st.warning('Failed to generate itinerary. Please try again.')
            
            st.rerun()
