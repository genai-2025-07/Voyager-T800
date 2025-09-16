import os
import re
import uuid

from datetime import datetime

import requests
import streamlit as st

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

st.set_page_config(page_title=APP_PAGE_TITLE, page_icon=APP_PAGE_ICON, layout='wide')


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
        if method_upper == 'GET':
            response = requests.get(url, params=params, timeout=30)
        elif method_upper == 'DELETE':
            response = requests.delete(url, params=params, timeout=30)
        elif method_upper == 'PUT':
            response = requests.put(url, json=data, timeout=30)
        elif method_upper == 'PATCH':
            response = requests.patch(url, json=data, timeout=30)
        else:
            response = requests.post(url, json=data, timeout=30)

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
        if method_upper == 'GET':
            response = requests.get(url, params=params, timeout=30)
        elif method_upper == 'DELETE':
            response = requests.delete(url, params=params, timeout=30)
        elif method_upper == 'PUT':
            response = requests.put(url, json=data, timeout=30)
        elif method_upper == 'PATCH':
            response = requests.patch(url, json=data, timeout=30)
        else:
            response = requests.post(url, json=data, timeout=30)
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


def transfer_sessions_api(from_user_id: str, to_user_id: str) -> dict | None:
    return call_api_endpoint(
        '/itinerary/sessions/transfer',
        {'from_user_id': from_user_id, 'to_user_id': to_user_id},
        method='POST',
    )


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


def generate_itinerary(user_message: str, session_id: str, user_id: str = 'anonymous') -> dict | None:
    """Generate itinerary and store it in DynamoDB using FastAPI backend."""
    data = {'query': user_message, 'session_id': session_id, 'user_id': user_id}
    result = call_api_endpoint('/itinerary/generate', data, method='POST')
    if result and 'itinerary' in result and 'itinerary_id' in result:
        return result
    return None


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
                    prev_user = st.session_state.user_id
                    prev_session = st.session_state.current_session_id
                    st.session_state.auth = auth_resp
                    st.session_state.user_id = auth_resp.get('user_sub') or auth_resp.get('email') or prev_user
                    prev_is_anon = prev_user == 'anonymous' or (
                        isinstance(prev_user, str) and prev_user.startswith('anon_')
                    )
                    if prev_user and prev_is_anon and st.session_state.user_id != prev_user and prev_session:
                        transfer_sessions_api(prev_user, st.session_state.user_id)
                    # Clear any anonymous session state to avoid showing an empty session
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


st.markdown('---')

user_input = st.chat_input(get_dynamic_chat_placeholder())

if user_input and user_input.strip():
    if not user_input.strip():
        st.warning('Your message is empty.')

    if len(user_input.strip()) > MAX_INPUT_LENGTH:
        st.warning(f'Message too long (max {MAX_INPUT_LENGTH} characters).')

    else:
        st.session_state.messages.append({'role': 'user', 'content': user_input.strip()})

    with st.spinner('Voyager-T800 is analyzing your request...'):
        # Generate itinerary and store in DynamoDB
        result = generate_itinerary(user_input.strip(), st.session_state.session_id, st.session_state.user_id)

        if result and isinstance(result, dict):
            assistant_response = result.get('itinerary', '')
            itinerary_id = result.get('itinerary_id', '')

            if assistant_response and assistant_response.strip():
                cleaned = assistant_response.strip().lower()
                if cleaned not in ['error', 'none', 'null']:
                    # Store the itinerary ID in the message for future reference
                    st.session_state.messages.append(
                        {'role': 'assistant', 'content': assistant_response.strip(), 'itinerary_id': itinerary_id}
                    )
                else:
                    st.warning('Assistant returned an error message, not saved.')
            else:
                st.warning('Assistant response is empty, not saved.')
        else:
            st.warning('Failed to generate itinerary. Please try again.')

    st.rerun()
