import logging
import os
import time

from dotenv import load_dotenv
from langchain.memory import ConversationSummaryMemory
from langchain.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_groq import ChatGroq

from app.memory.custom_summary_memory import SummaryChatMessageHistory
from app.utils.read_prompt_from_file import load_prompt_from_file


logger = logging.getLogger(__name__)

load_dotenv()  # Load environment variables from .env file

# Set your Groq API key in your environment variables
try:
    groq_key = os.getenv('GROQ_API_KEY')
except Exception as e:
    logger.error(f'ERROR exporting Groq API key: {e}')

# Initialize Groq LLM
# Parameterize model name and temperature via environment variables for flexibility
model_name = os.getenv('GROQ_MODEL_NAME', 'llama3-8b-8192')
temperature = float(os.getenv('GROQ_TEMPERATURE', '0.7'))

llm = ChatGroq(groq_api_key=groq_key, model=model_name, temperature=temperature, streaming=True)

try:
    itinerary_template = load_prompt_from_file('app/prompts/test_itinerary_prompt.txt')
    summary_template = load_prompt_from_file('app/prompts/test_summary_prompt.txt')
except Exception as e:
    logger.error(f'ERROR loading prompts: {e}')

prompt = PromptTemplate(input_variables=['chat_history', 'user_input'], template=itinerary_template)

memory_prompt = PromptTemplate(input_variables=['summary', 'new_lines'], template=summary_template)

# Configuration: expose token limit and session TTL via environment variables
try:
    MEMORY_MAX_TOKEN_LIMIT = int(os.getenv("SESSION_MEMORY_MAX_TOKEN_LIMIT", "1000"))
except Exception:
    MEMORY_MAX_TOKEN_LIMIT = 1000

try:
    SESSION_MEMORY_TTL_SECONDS = int(os.getenv("SESSION_MEMORY_TTL_SECONDS", "3600"))
except Exception:
    SESSION_MEMORY_TTL_SECONDS = 3600

memory = ConversationSummaryMemory(
    llm=llm,
    prompt=memory_prompt,
    max_token_limit=MEMORY_MAX_TOKEN_LIMIT
)

# Chain where we will pass the last message from the chat history
def extract_chat_history_content(x):
    """
    Safely extract the content of the last message from chat_history.
    Handles various possible input structures and errors.
    """
    try:
        chat_history = x.get('chat_history', [])
        if not isinstance(chat_history, list) or not chat_history:
            return ''
        last_msg = chat_history[-1]
        # Handle dict or object with 'content'
        if isinstance(last_msg, dict):
            return last_msg.get('content', '')
        elif hasattr(last_msg, 'content'):
            return getattr(last_msg, 'content', '')
        else:
            return str(last_msg)
    except Exception as e:
        logger.warning(f'WARNING: Failed to extract chat_history content: {e}')
        return ''


chain = RunnablePassthrough.assign(chat_history=extract_chat_history_content) | prompt | llm

session_memories = {}

def _cleanup_expired_sessions():
    """
    Remove session histories that have not been accessed within TTL to avoid memory leaks.
    No-op if TTL is non-positive.
    """
    try:
        ttl = SESSION_MEMORY_TTL_SECONDS
        now = time.time()
        expired_session_ids = []
        for s_id, entry in list(session_memories.items()):
            if not isinstance(entry, dict) or "last_access" not in entry:
                continue
            if now - entry["last_access"] > ttl:
                expired_session_ids.append(s_id)
        for s_id in expired_session_ids:
            del session_memories[s_id]
    except Exception as e:
        logging.warning(f"WARNING during session cleanup: {e}")

def get_session_memory(session_id:str):
    """
    Get or initialize a conversation memory instance for a given session.

    This function ensures that each session has its own dedicated
    `ConversationSummaryMemory` wrapped in `SummaryChatMessageHistory`
    to prevent cross-session memory bleed. If no memory exists for the
    provided session ID, a new one is created and stored.This function ensures each session has its own dedicated
    `ConversationSummaryMemory` wrapped in `SummaryChatMessageHistory`
    to prevent cross-session memory bleed.

    Features:
    - Cleans up expired sessions before returning memory.
    - Creates a new memory if none exists for the session.
    - Updates the session's last access time on each call.
    - Maintains backward compatibility with older plain history objects.

    Args: session_id (str): The unique identifier of the specific session.

    Returns: SummaryChatMessageHistory: an object that manages the chat history and conversation summary for the specified session.
    """
    _cleanup_expired_sessions()

    if llm is None:
        raise RuntimeError("LLM client is not initialized. Ensure 'llm' is configured before requesting session memory.")
    if memory_prompt is None:
        raise RuntimeError("Memory prompt is not initialized. Ensure 'memory_prompt' is configured before requesting session memory.")

    entry = session_memories.get(session_id)

    if entry is not None and not isinstance(entry, dict):
        entry = {"history": entry, "last_access": time.time()}
        session_memories[session_id] = entry

    if entry is None:
        session_summary_memory = ConversationSummaryMemory(
            llm=llm,
            prompt=memory_prompt,
            max_token_limit=MEMORY_MAX_TOKEN_LIMIT
        )
        history = SummaryChatMessageHistory(session_summary_memory)
        session_memories[session_id] = {"history": history, "last_access": time.time()}
        return history

    entry["last_access"] = time.time()
    return entry["history"]

# Wrapper for message history
runnable_with_history = RunnableWithMessageHistory(
    runnable=chain,
    # Always return the same memory object for session history
    # NOTE: If we need to handle multiple sessions, we can modify this to return different memory instances based on session_id
    get_session_history=lambda session_id: get_session_memory(session_id),
    input_messages_key='user_input',
    history_messages_key='chat_history',
)


def stream_response(user_input, session_id='default_session'):
    """
    Function to stream the response from the assistant (synchronous)
    """
    try:
        for chunk in runnable_with_history.stream(
            {'user_input': user_input}, config={'configurable': {'session_id': session_id}}
        ):
            content = chunk.content if hasattr(chunk, 'content') else str(chunk)

            print(content, end='', flush=True)
            time.sleep(0.05)  # Simulate a delay for streaming effect
    except Exception as e:
        logger.error(f'ERROR: {e}')


def full_response(user_input, session_id='default_session'):
    """
    Function to get the full response from the assistant without streaming (synchronous)
    """
    response = ''
    try:
        result = runnable_with_history.invoke(
            {'user_input': user_input}, config={'configurable': {'session_id': session_id}}
        )
        response = result.content if hasattr(result, 'content') else str(result)
        print(response, end='', flush=True)
        return response
    except Exception as e:
        logger.error(f'ERROR: {e}')


def main():
    """
    Main function to run the assistant
    """
    print('\n\nHey! I am your travel assistant. How can I help?')

    session_id = 'default_session'
    try:
        while True:
            user_input = input("\nQuery ('q' to quit): ")
            if user_input.lower() == 'q':
                break

            print('\n\nAnswer: ', end='')

            # Streaming response
            stream_response(user_input, session_id)

            # Response without streaming
            # full_response(user_input, session_id)

            # Debugging: Print current memory state
            # Uncomment the line below to see the memory state after each query
            # print(f"\n\nMemory: {memory.buffer}")
    except KeyboardInterrupt:
        logger.info('User interrupted the session.')


if __name__ == '__main__':
    main()
