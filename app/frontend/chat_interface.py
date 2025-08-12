import streamlit as st
from datetime import datetime
import asyncio
import sys
import os
import json
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from chains.itinerary_chain import full_response, stream_response, clear_session_memory


st.set_page_config(
    page_title="Voyager-T800 Travel Assistant", 
    page_icon="🚀",
    layout="wide"
)
with open(os.path.join(os.path.dirname(__file__), "style.css")) as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Initialize session state for chat history and sessions management
if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.messages.append({
        "role": "assistant",
        "content": "🚀 Welcome to Voyager-T800! I'm your intelligent AI travel assistant. Tell me about your dream trip - where would you like to go, when, and what kind of experience are you looking for?",
        "timestamp": datetime.now()
    })

if "user_input" not in st.session_state:
    st.session_state.user_input = ""

if "session_id" not in st.session_state:
    st.session_state.session_id = f"voyager_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

if "session_counter" not in st.session_state:
    st.session_state.session_counter = 1

# Initialize sessions management
if "sessions" not in st.session_state:
    st.session_state.sessions = {}
    initial_name = f"Trip Planning {st.session_state.session_counter}"
    st.session_state.sessions[st.session_state.session_id] = {
        "name": initial_name,
        "messages": st.session_state.messages.copy(),
        "created": datetime.now(),
    }
    st.session_state.session_counter += 1

if "current_session_id" not in st.session_state:
    st.session_state.current_session_id = st.session_state.session_id

def save_current_session():
    """Save the current session to sessions storage"""
    # Get existing session data or create new minimal metadata
    existing_session = st.session_state.sessions.get(st.session_state.current_session_id, {})
    session_name = existing_session.get("name", f"Trip Planning {st.session_state.session_counter}")

    session_data = {
        "name": session_name,
        "messages": st.session_state.messages.copy(),
        "created": existing_session.get("created", datetime.now()),
    }
    st.session_state.sessions[st.session_state.current_session_id] = session_data


def load_session(session_id):
    """Load a specific session"""
    if session_id in st.session_state.sessions:
        st.session_state.current_session_id = session_id
        st.session_state.messages = st.session_state.sessions[session_id]["messages"].copy()
        st.session_state.session_id = session_id


def create_new_session():
    """Create a new session"""
    # Save current session before creating new one
    if st.session_state.messages:
        save_current_session()

    new_session_id = f"voyager_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    st.session_state.current_session_id = new_session_id
    st.session_state.session_id = new_session_id
    st.session_state.messages = [{
        "role": "assistant",
        "content": "🚀 Welcome to Voyager-T800! I'm your intelligent AI travel assistant. Tell me about your dream trip - where would you like to go, when, and what kind of experience are you looking for?",
        "timestamp": datetime.now()
    }]

    # Create session with descriptive, monotonic name
    session_name = f"Trip Planning {st.session_state.session_counter}"
    st.session_state.sessions[new_session_id] = {
        "name": session_name,
        "messages": st.session_state.messages.copy(),
        "created": datetime.now(),
    }
    st.session_state.session_counter += 1


def delete_session(session_id):
    """Delete a session"""
    if session_id in st.session_state.sessions:
        del st.session_state.sessions[session_id]
        # Clear the AI memory for this session
        clear_session_memory(session_id)
        if session_id == st.session_state.current_session_id:
            # If we deleted the current session, create a new one
            create_new_session()


def run_ai_response(user_message, session_id):
    """
    Wrapper to run your existing async AI response in Streamlit
    """
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        response = loop.run_until_complete(full_response(user_message, session_id))
        loop.close()
        return response
    except Exception as e:
        return f"❌ Error in AI processing: {str(e)}"


def clear_chat():
    """Clear chat history"""
    st.session_state.messages = []
    st.session_state.messages.append({
        "role": "assistant",
        "content": "🚀 Welcome back to Voyager-T800! I'm ready to help you plan another amazing trip. What's your next destination?",
        "timestamp": datetime.now()
    })
    save_current_session()

st.title("🚀 Voyager-T800 Travel Assistant")
st.markdown("*Your AI-powered conversational trip planner*")

# Sidebar with sessions history and controls
with st.sidebar:
    st.header("💬 Sessions")

    if st.button("➕ New Session", type="primary", use_container_width=True):
        create_new_session()
        st.rerun()

    st.markdown("---")

    # Sessions list
    if st.session_state.sessions:
        st.subheader("📚 Session History")

        for session_id, session_data in st.session_state.sessions.items():
            with st.container():
                session_name = session_data["name"]
                created_date = session_data["created"].strftime("%m/%d")

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
                        unsafe_allow_html=True
                    )
                else:
                    if st.button(
                        f" {session_name}",
                        key=f"session_{session_id}",
                        help=f"Click to switch to {session_name}",
                        use_container_width=True
                    ):
                        load_session(session_id)
                        st.rerun()

                    st.caption(f"Created: {created_date}")

                if len(st.session_state.sessions) > 1:
                    if st.button("🗑️ Delete", key=f"delete_{session_id}", help=f"Delete {session_name}"):
                        delete_session(session_id)
                        st.rerun()

                st.markdown("---")

    st.markdown("---")
    st.header("Chat Controls")
    if st.button("🗑️ Clear Chat", type="secondary", use_container_width=True):
        clear_chat()
        st.rerun()

    st.markdown("---")
    st.subheader("💡 Tips")
    st.markdown("""
    Try asking:
    - "Plan a 5-day trip to Japan"
    - "I want a relaxing beach vacation"
    - "Make day 3 more adventurous"
    - "What's the best time to visit?"
    """)

    st.markdown("---")
    st.subheader("ℹ️ About")
    st.markdown("Voyager-T800 uses your custom itinerary chain with Llama3-8B to create personalized travel itineraries.")

# Main chat interface
chat_container = st.container()

with chat_container:
    for i, message in enumerate(st.session_state.messages):
        if message["role"] == "user":
            st.markdown(
                f"""
                <div class="message-container">
                    <div class ="message-bubble">
                        {message['content']}
                    </div>
                </div>
                """, 
                unsafe_allow_html=True
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
                unsafe_allow_html=True
            )

# Input area
st.markdown("---")

user_input = st.chat_input("Type your travel plans or questions...")

if user_input and user_input.strip():
    st.session_state.messages.append({
        "role": "user",
        "content": user_input.strip(),
        "timestamp": datetime.now()
    })

    with st.spinner(" Voyager-T800 is analyzing your request and crafting your itinerary..."):
        assistant_response = run_ai_response(user_input.strip(), st.session_state.session_id)

    st.session_state.messages.append({
        "role": "assistant",
        "content": assistant_response,
        "timestamp": datetime.now()
    })

    save_current_session()

    st.rerun()