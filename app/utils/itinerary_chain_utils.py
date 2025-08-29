from app.retrieval.prototype_retriever import RAGPrototype
import logging
from dotenv import load_dotenv
import os

load_dotenv()  # Load environment variables from .env file
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'

logger = logging.getLogger(__name__)

def extract_chat_history_content(x):
    """
    Safely extract the content of the last message from chat_history.
    Handles various possible input structures and errors.
    Args:
        x (dict): Input dictionary containing 'chat_history'.
    """
    try:
        chat_history = x.get("chat_history", [])
        if not isinstance(chat_history, list) or not chat_history:
            return ""
        last_msg = chat_history[-1]
        # Handle dict or object with 'content'
        if isinstance(last_msg, dict):
            return last_msg.get("content", "")
        elif hasattr(last_msg, "content"):
            return getattr(last_msg, "content", "")
        else:
            return str(last_msg)
    except Exception as e:
        logger.warning(f"WARNING: Failed to extract chat_history content: {e}")
        return ""
    
# Function to format retrieved documents with sources and city for context
def format_docs(docs):
    """
    Format retrieved documents with their source and city metadata.
    Args:
        docs (list): List of retrieved document objects with metadata.
    """
    if DEBUG:
        print("\n\n--- Retrieved Docs ---")
        for d in docs:
            print(f"Source: {d.metadata.get('source', 'unknown')}")
            print(f"City: {d.metadata.get('city', 'unknown')}")
            print(f"Content: {str(d.page_content)[:200]}...\n")
        print("--- End Retrieved Docs ---\n\n")

    return "\n\n".join(
        f"Source: {doc.metadata.get('source', 'unknown')}\nCity: {doc.metadata.get('city', 'unknown')}\nContent: {doc.page_content.strip()}"
        for doc in docs
    )

def get_rag_retriever():
    rag = RAGPrototype(os.getenv("EMBEDDINGS_DIR", "data/embeddings"))
    return rag.get_retriever()