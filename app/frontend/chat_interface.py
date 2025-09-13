import copy
import io
import os
import re

from contextlib import redirect_stdout
from datetime import datetime

import requests
import streamlit as st


# Configuration
API_BASE_URL = os.environ.get('API_BASE_URL', 'http://localhost:8000')
STREAMLIT_ENV = os.environ.get('STREAMLIT_ENV', 'dev')

WELCOME_MESSAGE = (
    "🚀 Welcome to Voyager-T800! I'm your intelligent AI travel assistant. "
    'Tell me about your dream trip - where would you like to go, when, and what kind of experience are you looking for?'
)

APP_PAGE_TITLE = os.environ.get('VOYAGER_PAGE_TITLE', 'Voyager-T800 Travel Assistant')
APP_PAGE_ICON = os.environ.get('VOYAGER_PAGE_ICON', '🚀')
APP_PAGE_TAGLINE = os.environ.get(
    'VOYAGER_PAGE_TAGLINE',
    '*Your AI-powered conversational trip planner*',
)

try:
    MAX_INPUT_LENGTH = int(os.environ.get('VOYAGER_MAX_INPUT_LENGTH', '500'))
except ValueError:
    MAX_INPUT_LENGTH = 500

try:
    SESSIONS_PAGE_SIZE = int(os.environ.get('VOYAGER_SESSIONS_PAGE_SIZE', '10'))
except ValueError:
    SESSIONS_PAGE_SIZE = 10

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
    st.session_state.user_id = 'anonymous'

if 'sessions' not in st.session_state:
    st.session_state.sessions = {}

if 'current_session_id' not in st.session_state:
    st.session_state.current_session_id = None

if 'sessions_page' not in st.session_state:
    st.session_state.sessions_page = 1

if 'confirm_delete' not in st.session_state:
    st.session_state.confirm_delete = None


# API communication functions
def call_api_endpoint(endpoint: str, data: dict) -> dict | None:
    """Make API call to FastAPI backend."""
    try:
        url = f'{API_BASE_URL}/api/v1{endpoint}'
        response = requests.post(url, json=data, timeout=30)

        if response.status_code == 200:
            return response.json()
        else:
            st.error(f'API Error: {response.status_code} - {response.text}')
            return None

    except requests.exceptions.RequestException as e:
        st.error('Connection Error: Unable to connect to the API server. Please check if the backend is running.')
        if STREAMLIT_ENV == 'dev':
            st.error(f'Debug info: {str(e)}')
        return None
    except Exception as e:
        st.error(f'Unexpected Error: {str(e)}')
        return None


def generate_itinerary(user_message: str, session_id: str, user_id: str = 'anonymous') -> dict | None:
    """Generate itinerary and store it in DynamoDB using FastAPI backend."""
    data = {'query': user_message, 'session_id': session_id, 'user_id': user_id}

    result = call_api_endpoint('/itinerary/generate', data)
    if result and 'itinerary' in result and 'itinerary_id' in result:
        return result
    return None


def get_session_data(session_id: str, user_id: str = 'anonymous') -> dict | None:
    """Retrieve session data by session_id using FastAPI backend."""
    try:
        url = f'{API_BASE_URL}/api/v1/itinerary/{session_id}?user_id={user_id}'
        response = requests.get(url, timeout=30)

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            return None
        else:
            st.error(f'API Error: {response.status_code} - {response.text}')
            return None

    except requests.exceptions.RequestException as e:
        st.error('Connection Error: Unable to connect to the API server.')
        if STREAMLIT_ENV == 'dev':
            st.error(f'Debug info: {str(e)}')
        return None
    except Exception as e:
        st.error(f'Unexpected Error: {str(e)}')
        return None


def create_new_session_api(user_id: str = 'anonymous') -> dict | None:
    """Create a new session via API."""
    try:
        data = {'user_id': user_id}
        result = call_api_endpoint('/itinerary/sessions', data)

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
    # Create initial session via API
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
        # Add to local sessions cache
        st.session_state.sessions[session_data['session_id']] = {
            'name': f'Trip Planning {len(st.session_state.sessions) + 1}',
            'messages': copy.deepcopy(st.session_state.messages),
            'created': session_data['created'],
        }
    else:
        st.error('Failed to initialize session. Please refresh the page.')
        st.stop()


def _sync_session_counter_with_existing_names():
    """
    Ensure session_counter is always one greater than the highest numeric suffix
    used in session names like 'Trip Planning N'. Prevents duplicate names
    after deletions or manual edits.
    """
    try:
        max_suffix = 0
        pattern = re.compile(r'^Trip Planning (\d+)$')
        for session in st.session_state.sessions.values():
            name = session.get('name', '')
            match = pattern.match(name)
            if match:
                try:
                    suffix = int(match.group(1))
                    if suffix > max_suffix:
                        max_suffix = suffix
                except ValueError:
                    continue
        st.session_state.session_counter = max(max_suffix + 1, st.session_state.session_counter)
    except Exception:
        # Fallback: don't change the counter on error
        pass


def save_current_session():
    """Save the current session to local cache (API handles persistence)"""
    existing_session = st.session_state.sessions.get(st.session_state.current_session_id, {})

    desired_name = existing_session.get('name')
    if not desired_name:
        desired_name = f'Trip Planning {len(st.session_state.sessions) + 1}'

    session_data = {
        'name': desired_name,
        'messages': st.session_state.messages.copy(),
        'created': existing_session.get('created', datetime.now()),
    }
    st.session_state.sessions[st.session_state.current_session_id] = session_data


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

    # Update local cache
    st.session_state.sessions[session_id] = {
        'name': f'Trip Planning {len(st.session_state.sessions) + 1}',
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

        # Add to local sessions cache
        session_name = f'Trip Planning {len(st.session_state.sessions) + 1}'
        st.session_state.sessions[session_data['session_id']] = {
            'name': session_name,
            'messages': st.session_state.messages.copy(),
            'created': session_data['created'],
        }
    else:
        st.error('Failed to create new session. Please try again.')


def delete_session(session_id):
    """Delete a session"""
    if session_id in st.session_state.sessions:
        del st.session_state.sessions[session_id]


class StreamlitWriter(io.StringIO):
    def __init__(self, placeholder):
        super().__init__()
        self.placeholder = placeholder

    def write(self, s):
        super().write(s)
        self.placeholder.markdown(self.getvalue())


def run_ai_stream(user_message: str, session_id: str):
    """
    Stream the AI model's response to a Streamlit placeholder and capture the output.

    This function sends the user's message to the AI model associated with a
    specific session, streams the response in real-time to the Streamlit UI,
    and captures the full response as a string.

    Args:
        user_message (str): The message from the user to send to the AI model.
        session_id (str): The unique identifier of the session, used to retrieve
                          or maintain session-specific conversation memory.

    Returns:
        str: The complete AI-generated response captured from the stream.
    """
    from app.chains.itinerary_chain import stream_response

    placeholder = st.empty()
    writer = StreamlitWriter(placeholder)
    with redirect_stdout(writer):
        stream_response(user_message, session_id)
    return writer.getvalue()


def run_ai_response(user_message: str, session_id: str):
    """
    Run the synchronous `full_response` and capture its printed output as a string.

    Args:
        user_message (str): The user's input message to be sent to the AI.
        session_id (str): The unique identifier for the session to maintain
                          session-specific memory and context.

    Returns:
        str: The captured AI output, or an error message if an exception occurs.
    """
    from app.chains.itinerary_chain import full_response

    try:
        import io

        from contextlib import redirect_stdout

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            full_response(user_message, session_id)
        return buffer.getvalue()
    except Exception as e:
        return f'Error in AI processing: {str(e)}'


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
    st.header('💬 Sessions')

    if st.button('➕ New Session', type='primary', use_container_width=True):
        create_new_session()
        st.rerun()

    st.markdown('---')

    if st.session_state.sessions:
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
        total_sessions = len(sessions_items)
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
        visible_sessions = sessions_items[start_idx:end_idx]

        for session_id, session_data in visible_sessions:
            with st.container():
                session_name = session_data['name']
                created_date = session_data['created'].strftime('%m/%d')

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

                if len(st.session_state.sessions) > 1:
                    if st.button('🗑️ Delete', key=f'delete_{session_id}', help=f'Delete {session_name}'):
                        st.session_state.confirm_delete = session_id

                if st.session_state.confirm_delete == session_id:
                    st.warning(f"Are you sure you want to delete '{session_name}'?")
                    if st.button('✅ Yes, delete', key=f'confirm_{session_id}'):
                        delete_session(session_id)
                        st.session_state.confirm_delete = None
                        st.rerun()
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

    save_current_session()

    st.rerun()
