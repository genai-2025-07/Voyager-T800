from memory.async_summary import AsyncConversationSummaryMemory
from langchain_groq import ChatGroq
from langchain.prompts import PromptTemplate
from langchain_core.runnables.history import RunnableWithMessageHistory
import asyncio
import os
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file

# Enter your Groq API key here or set it in your environment variables
#groq_key = os.environ["GROQ_API_KEY"] = "your-groq-api-key"
groq_key = os.getenv("GROQ_API_KEY")

# Initialize Groq LLM
llm = ChatGroq(
    groq_api_key=groq_key,
    model="llama3-8b-8192",
    temperature=0.7,
    streaming=True
)

# Initialize custom memory
memory = AsyncConversationSummaryMemory(
    llm=llm,
    memory_key="chat_history",
    max_token_limit=500
)

# Prompt template for generating travel itineraries
template = """You are an intelligent travel assistant designed to create detailed and structured travel itineraries. 
Your goal is to provide personalized, concise, and informative recommendations based on the user's query and conversation history. 
When generating an itinerary, structure it by days, with activities divided into Morning, Afternoon, and Evening. 
Include specific locations, activity types (e.g., cultural, gastronomic, outdoor), and practical details like transport options and estimated time for each activity. 
If the user specifies a budget, tailor recommendations to it, offering alternatives for different budget levels if relevant. 
Ensure responses are clear, structured as lists, and prioritize user preferences from the conversation history.

Previous conversation: {chat_history}

User query: {user_input}

Response: """

prompt = PromptTemplate(
    input_variables=["chat_history", "user_input"],
    template=template
)

# Prompt template for summary of the conversation
summary_template = """Progressively summarize the lines of conversation provided, adding onto the previous summary, returning a new summary. If a travel itinerary was generated, preserve all details of the itinerary (including specific days and locations) exactly as provided, without modifications, and include it at the end of the summary under the heading "Saved Itinerary".

EXAMPLE
Current summary:
The human asked for a 2-day itinerary in Rome. The AI provided a detailed schedule.

New lines of conversation:
Human: Create a 2-day itinerary for Rome.
AI: Day 1:
- Morning: Visit Colosseum
- Afternoon: Explore Roman Forum
- Evening: Dinner at Trastevere
Day 2:
- Morning: Tour Vatican Museums
- Afternoon: St. Peter’s Basilica
- Evening: Walk along Tiber River

New summary:
The human asked for a 2-day itinerary in Rome. The AI provided a detailed schedule.

Saved Itinerary:
Day 1:
- Morning: Visit Colosseum
- Afternoon: Explore Roman Forum
- Evening: Dinner at Trastevere
Day 2:
- Morning: Tour Vatican Museums
- Afternoon: St. Peter’s Basilica
- Evening: Walk along Tiber River
END OF EXAMPLE

Current summary:
{summary}

New lines of conversation:
{new_lines}

New summary: """

memory.prompt = PromptTemplate(
    input_variables=["summary", "new_lines"],
    template=summary_template
)

# Chain
chain = prompt | llm

# Wrapper for message history
runnable_with_history = RunnableWithMessageHistory(
    runnable=chain,
    # Always return the same memory object for session history
    # NOTE: If we need to handle multiple sessions, we can modify this to return different memory instances based on session_id
    get_session_history=lambda session_id: memory,
    input_messages_key="user_input",
    history_messages_key="chat_history"
)

async def stream_response(user_input, session_id="default_session"):
    """
    Function to stream the response from the assistant
    """
    response = ""
    try:
        async for chunk in runnable_with_history.astream(
            {"user_input": user_input},
            config={"configurable": {"session_id": session_id}}
        ):
            content = chunk.content if hasattr(chunk, 'content') else str(chunk)
            response += content
            print(content, end='', flush=True)
            await asyncio.sleep(0.1)
    except Exception as e:
        print(f"\nERROR: {e}")
    return response

async def full_response(user_input, session_id="default_session"):
    """
    Function to get the full response from the assistant without streaming
    """
    response = ""
    try:
        result = await runnable_with_history.ainvoke(
            {"user_input": user_input},
            config={"configurable": {"session_id": session_id}}
        )
        response = result.content if hasattr(result, 'content') else str(result)
        print(response)
    except Exception as e:
        print(f"\nERROR: {e}")
    return response

async def main():
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
        await stream_response(user_input, session_id)
        
        # Response without streaming
        #await full_response(user_input, session_id)
        print(f"\n\nMemory: {memory.load_memory_variables({'session_id': session_id})['chat_history']}")

if __name__ == "__main__":
    asyncio.run(main())