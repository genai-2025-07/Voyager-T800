from langchain.memory import ConversationSummaryMemory
from langchain_core.messages import AIMessage, HumanMessage, BaseMessage
from typing import List

# Custom wrapper for conversation summary memory to handle async operations
# NOTE: Using sync calls inside async methods — may block for large memory
class AsyncConversationSummaryMemory(ConversationSummaryMemory):
    async def aget_messages(self, session_id: str = "") -> List[BaseMessage]:
        # Asynchronously retrieve messages for the given session
        memory_data = self.load_memory_variables({"session_id": session_id})
        history = memory_data.get("chat_history", "")
        return [AIMessage(content=history)] if history else []

    async def aadd_messages(self, messages: List[BaseMessage]):
        # Asynchronously add messages to the memory
        human_msg = None
        ai_msg = None
        for message in messages:
            if isinstance(message, HumanMessage):
                human_msg = message.content
            elif isinstance(message, AIMessage):
                ai_msg = message.content
        if human_msg is not None or ai_msg is not None:
            self.save_context(
                inputs={"input": human_msg or ""},
                outputs={"output": ai_msg or ""}
            )