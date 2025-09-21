from dotenv import load_dotenv
import logging
import os
import time


from app.utils.read_prompt_from_file import read_prompt_from_file
from app.utils.itinerary_chain_utils import extract_chat_history_content, format_docs, get_rag_retriever
from app.utils.date_utils import extract_date_range, derive_city_from_text
from app.services.weather import get_weather_forecast_sync
from app.services.weaviate.weaviate_setup import setup_complete_database
from app.retrieval.waiss_retriever import setup_rag_retriever
from app.memory.custom_summary_memory import SummaryChatMessageHistory
from langchain.memory import ConversationSummaryMemory
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_groq import ChatGroq
from langchain.prompts import PromptTemplate

# Configure logging
if not logging.getLogger().hasHandlers():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )
logger = logging.getLogger('app.chains.itinerary_chain')

load_dotenv()  # Load environment variables from .env file

# Set your Groq API key in your environment variables
try:
    groq_key = os.getenv("GROQ_API_KEY")
except Exception as e:
    logger.error(f"ERROR exporting Groq API key: {e}")

# Initialize Groq LLM
# Parameterize model name and temperature via environment variables for flexibility
model_name = os.getenv("GROQ_MODEL_NAME", "llama3-8b-8192")
temperature = float(os.getenv("GROQ_TEMPERATURE", "0.7"))

llm = ChatGroq(
    groq_api_key=groq_key,
    model=model_name,
    temperature=temperature,
    streaming=True
)

try:
    db_manager, client_wrapper, result = setup_complete_database()
except Exception as e:
    logger.error(f"ERROR setting up database: {e}")

try:
    itinerary_template = read_prompt_from_file("app/prompts/test_itinerary_prompt.txt")
    summary_template = read_prompt_from_file("app/prompts/test_summary_prompt.txt")
except Exception as e:
    logger.error(f"ERROR loading prompts: {e}")

prompt = PromptTemplate(
    input_variables=["chat_history", "user_input", "context", "weather_context"],
    template=itinerary_template
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

# Chain where we will pass the last message from the chat history
def _build_weather_context(payload: dict) -> str:
    
    """Derive city and dates from the user input, fetch weather, and format a compact context string.

    This function is defensive: if anything fails, it returns an empty string so the LLM falls back gracefully.
    """
    try:
        user_text = payload.get("user_input", "")
        
        if not isinstance(user_text, str) or not user_text.strip():
            return ""

        # City heuristic extracted via utility function
        city = derive_city_from_text(user_text)
        if not city:
            return ""

        start_dt, end_dt = extract_date_range(user_text)

        # Read UI-provided flag via environment variable for thin-client compliance
        use_weather_env = os.getenv("VOYAGER_USE_WEATHER", "1").strip()
        use_weather = use_weather_env not in ("0", "false", "False")
        if not use_weather:
            return ""

        weather_json = get_weather_forecast_sync(
            project_root=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")),
            city=city,
            start_date=start_dt,
            end_date=end_dt,
        )

        if not isinstance(weather_json, dict) or weather_json.get("disabled") or weather_json.get("error"):
            return ""

        days = weather_json.get("days", [])
        if not days:
            return ""

        # Compact, LLM-friendly weather block. Keep it minimal and deterministic.
        lines = [
            "<weather>",
            f"city={weather_json.get('city','')} units={weather_json.get('units','metric')}",
        ]
        for d in days:
            lines.append(
                f"{d['date']} label={d['label']} tmin={d['temp_min_c']}C tmax={d['temp_max_c']}C precip={d['precipitation_mm']}mm wind={d['wind_mps']}mps desc={d['description']}"
            )
        lines.append("</weather>")

        weather_context_str = "\n".join(lines)
        logger.info(f"Weather context generated for user_input '{user_text}':\n{weather_context_str}")
        
        return weather_context_str
    except Exception:
        return ""


chain = RunnablePassthrough.assign(
    chat_history=extract_chat_history_content,
    context=RunnableLambda(lambda x: format_docs(retriever.invoke(x["user_input"]))), # Format retrieved documents with sources and city for context
    weather_context=RunnableLambda(_build_weather_context),
) | prompt | llm

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

def stream_response(user_input, session_id="default_session"):
    """
    Function to stream the response from the assistant (synchronous)
    """
    try:
        for chunk in runnable_with_history.stream(
            {"user_input": user_input},
            config={"configurable": {"session_id": session_id}}
        ):
            content = chunk.content if hasattr(chunk, 'content') else str(chunk)
            
            print(content, end='', flush=True)
            time.sleep(0.025)  # Simulate a delay for streaming effect
    except Exception as e:
        logger.error(f"ERROR: {e}")
        

def full_response(user_input, session_id="default_session"):
    """
    Function to get the full response from the assistant without streaming (synchronous)
    """
    response = ""
    try:
        result = runnable_with_history.invoke(
            {"user_input": user_input},
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