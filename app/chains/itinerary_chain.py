import logging
import os
import time


from app.utils.read_prompt_from_file import read_prompt_from_file
from app.utils.itinerary_chain_utils import extract_chat_history_content, format_docs, get_rag_retriever
from app.services.weaviate.weaviate_setup import setup_complete_database
from app.retrieval.waiss_retriever import setup_rag_retriever
from app.memory.custom_summary_memory import SummaryChatMessageHistory
from langchain.memory import ConversationSummaryMemory
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain.prompts import PromptTemplate
from app.models.llms.llm_factory import get_llm
from app.services.events.service import EventsService
from app.services.events.providers.tavily import TavilyEventsProvider
from app.services.events.models import EventQuery
from app.utils.events_utils import parse_event_query

# Configure logging
if not logging.getLogger().hasHandlers():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )
logger = logging.getLogger('app.chains.itinerary_chain')

llm = get_llm("groq")
structured_llm = llm.with_structured_output(schema=EventQuery)

events_service = EventsService(provider=TavilyEventsProvider())

try:
    db_manager, client_wrapper, result = setup_complete_database()
except Exception as e:
    logger.error(f"ERROR setting up database: {e}")

try:
    itinerary_template = read_prompt_from_file("app/prompts/expert_prompt_for_langchain.txt")
    summary_template = read_prompt_from_file("app/prompts/test_summary_prompt.txt")
except Exception as e:
    logger.error(f"ERROR loading prompts: {e}")
    raise e

prompt = PromptTemplate(
    input_variables=["chat_history", "user_input", "context", "events"],
    template=itinerary_template,
    template_format="jinja2"
)

memory_prompt = PromptTemplate(
    input_variables=["summary", "new_lines"],
    template=summary_template
)

# Configuration: expose token limit and session TTL via environment variables
try:
    MEMORY_MAX_TOKEN_LIMIT = int(os.getenv("SESSION_MEMORY_MAX_TOKEN_LIMIT", "1000"))
except Exception:
    MEMORY_MAX_TOKEN_LIMIT = 1000

try:
    SESSION_MEMORY_TTL_SECONDS = int(os.getenv("SESSION_MEMORY_TTL_SECONDS", "3600"))  
except Exception:
    SESSION_MEMORY_TTL_SECONDS = 3600

# Initialize RAG and retriever
if db_manager is None:
    raise RuntimeError("Database manager not initialized")
retriever = setup_rag_retriever(
    db=db_manager
)

tags = ["museum", "point_of_interest"]  # Example tags for filtering

# Chain where we will pass the last message from the chat history
chain = (RunnablePassthrough.assign(
    chat_history=extract_chat_history_content,
    context=RunnableLambda(lambda x: format_docs(retriever.invoke(x["user_input"], tags=tags))),  # Format retrieved documents with sources and city for context
    event_query=lambda x: parse_event_query(x["user_input"], structured_llm) if x.get("include_events") else None,
    )
    .assign(events=lambda x: events_service.get_events_for_itinerary(x["event_query"]) if x.get("include_events") and x.get("event_query") else "")
    | prompt | llm
)

session_memories = {}

def _cleanup_expired_sessions():
    """
    Remove session histories that have not been accessed within TTL to avoid memory leaks.
    No-op if TTL is non-positive.
    """
    try:
        ttl = SESSION_MEMORY_TTL_SECONDS
        if ttl <= 0:
            return  
        
        now = time.time()
        expired_session_ids = []
        for s_id, entry in list(session_memories.items()):
            if not isinstance(entry, dict) or "last_access" not in entry:
                logger.warning(f"Malformed session entry for {s_id}: {entry}")
                continue
            if now - entry["last_access"] > ttl:
                expired_session_ids.append(s_id)
        for s_id in list(expired_session_ids):
            del session_memories[s_id]
    except Exception as e:
        logger.warning(f"Session cleanup failed: {e}")

def get_session_memory(session_id:str):
    """
    Get or initialize conversation memory for a session.

    Each session gets its own `ConversationSummaryMemory` wrapped in 
    `SummaryChatMessageHistory`, preventing cross-session memory leaks.
    Expired sessions are cleaned up, new memory is created if needed,
    and the last access time is updated on each call.

    Args:
        session_id (str): Unique session identifier.

    Returns:
        SummaryChatMessageHistory: Manages chat history and summaries for the session.
    """

    _cleanup_expired_sessions()

    if llm is None:
        raise RuntimeError(f"LLM client is not initialized (llm={llm}). Ensure 'llm' is configured before requesting session memory.")
    if memory_prompt is None:
        raise RuntimeError("Memory prompt is not initialized (memory_prompt={memory_prompt}). Ensure 'memory_prompt' is configured before requesting session memory.")

    entry = session_memories.get(session_id)

    if entry is not None and not isinstance(entry, dict):
        raise TypeError("Session memory entry must be a dict, got type: {}".format(type(entry)))

    
    if entry is None:
        try:
            session_summary_memory = ConversationSummaryMemory(
            llm=llm,
            prompt=memory_prompt,
            max_token_limit=MEMORY_MAX_TOKEN_LIMIT
            )
            history = SummaryChatMessageHistory(session_summary_memory)
            if not isinstance(history, SummaryChatMessageHistory):
                raise TypeError("Failed to initialize SummaryChatMessageHistory.")
        
            session_memories[session_id] = {"history": history, "last_access": time.time()}
            return session_memories[session_id]["history"]
        except Exception as e:
            logger.error(f"Failed to initialize ConversationSummaryMemory: {e}")
            raise

    if time.time() - entry["last_access"] > 10:
        entry["last_access"] = time.time()
        return entry["history"]   
    return entry["history"]    


# Wrapper for message history
runnable_with_history = RunnableWithMessageHistory(
    runnable=chain,
    # Always return the same memory object for session history
    # NOTE: If we need to handle multiple sessions, we can modify this to return different memory instances based on session_id
    get_session_history=get_session_memory,
    input_messages_key="user_input",
    history_messages_key="chat_history"
)

def stream_response(user_input, session_id="default_session", include_events: bool = False):
    """
    Function to stream the response from the assistant (synchronous)
    """
    try:
        for chunk in runnable_with_history.stream(
            {"user_input": user_input, "include_events": include_events},
            config={"configurable": {"session_id": session_id}}
        ):
            content = chunk.content if hasattr(chunk, 'content') else str(chunk)
            
            print(content, end='', flush=True)
            time.sleep(0.025)  # Simulate a delay for streaming effect
    except Exception as e:
        logger.error(f"ERROR: {e}")
        raise e

def full_response(user_input, session_id="default_session", include_events: bool = False):
    """
    Function to get the full response from the assistant without streaming (synchronous)
    """
    response = ""
    try:
        result = runnable_with_history.invoke(
            {"user_input": user_input, "include_events": include_events},
            config={"configurable": {"session_id": session_id}}
        )
        response = result.content if hasattr(result, 'content') else str(result)
        print(response, end='', flush=True)
    except Exception as e:
        logger.error(f"ERROR: {e}")

def main():
    """
    Main function to run the assistant
    """
    print("\n\nHey! I am your travel assistant. How can I help?")
    
    session_id = "default_session"
    try:
        while True:
            user_input = input("\nQuery ('q' to quit): ")
            if user_input.lower() == 'q':
                break
            # elif user_input.lower() == 'mem':
            #     print(f"\n\nMemory: {memory.buffer}")
            #     continue

            print("\n\nAnswer: ", end='')

            # Streaming response
            stream_response(user_input, session_id)

            # Response without streaming
            #full_response(user_input, session_id)

            # Debugging: Print current memory state
            # Uncomment the line below to see the memory state after each query
            #print(f"\n\nMemory: {memory.buffer}")
    except KeyboardInterrupt:
        logger.info("User interrupted the session.")

if __name__ == "__main__":
    main()