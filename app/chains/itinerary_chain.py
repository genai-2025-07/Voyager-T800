from langchain.memory import ConversationSummaryMemory
from langchain_core.runnables import RunnablePassthrough
from langchain_groq import ChatGroq
from langchain.prompts import PromptTemplate
from langchain_core.runnables.history import RunnableWithMessageHistory
import os
import time
from app.utils.read_prompt_from_file import load_prompt_from_file
from app.memory.custom_summary_memory import SummaryChatMessageHistory
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file

# Set your Groq API key in your environment variables
groq_key = os.getenv("GROQ_API_KEY")

# Initialize Groq LLM
llm = ChatGroq(
    groq_api_key=groq_key,
    model="llama3-8b-8192",
    temperature=0.7,
    streaming=True
)

try:
    itinerary_template = load_prompt_from_file("app/prompts/test_itinerary_prompt.txt")
    summary_template = load_prompt_from_file("app/prompts/test_summary_prompt.txt")
except Exception as e:
    print(f"ERROR loading prompts: {e}")
    exit(1)

prompt = PromptTemplate(
    input_variables=["chat_history", "user_input"],
    template=itinerary_template
)

memory = ConversationSummaryMemory(llm=llm)

memory.prompt = PromptTemplate(
    input_variables=["summary", "new_lines"],
    template=summary_template
)

# Chain where we will pass the last message from the chat history
chain = RunnablePassthrough.assign(
    chat_history=lambda x: x["chat_history"][0].content if x["chat_history"] else ""
) | prompt | llm

# Wrapper for message history
runnable_with_history = RunnableWithMessageHistory(
    runnable=chain,
    # Always return the same memory object for session history
    # NOTE: If we need to handle multiple sessions, we can modify this to return different memory instances based on session_id
    get_session_history=lambda session_id: SummaryChatMessageHistory(memory),
    input_messages_key="user_input",
    history_messages_key="chat_history"
)

def stream_response(user_input, session_id="default_session"):
    """
    Function to stream the response from the assistant (synchronous)
    """
    response = ""
    try:
        for chunk in runnable_with_history.stream(
            {"user_input": user_input},
            config={"configurable": {"session_id": session_id}}
        ):
            content = chunk.content if hasattr(chunk, 'content') else str(chunk)
            response += content
            print(content, end='', flush=True)
            # time.sleep(0.1)  # Simulate a delay for streaming effect
    except Exception as e:
        print(f"\nERROR: {e}")
    return response

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
        print(response)
    except Exception as e:
        print(f"\nERROR: {e}")
    return response

def main():
    """
    Main function to run the assistant
    """
    print("\n\nHey! I am your travel assistant. How can I help?")
    
    session_id = "default_session"
    while True:
        user_input = input("\nQuery ('q' to quit): ")
        if user_input.lower() == 'q':
            break
            
        print("\n\nAnswer: ", end='')

        # Streaming response
        stream_response(user_input, session_id)
        
        # Response without streaming
        #full_response(user_input, session_id)

        # Debugging: Print current memory state
        # Uncomment the line below to see the memory state after each query
        print(f"\n\nMemory: {memory.buffer}")

if __name__ == "__main__":
    main()