from langchain_core.messages import BaseMessage, SystemMessage
from langchain_core.chat_history import BaseChatMessageHistory
from langchain.memory import ConversationSummaryMemory

class SummaryChatMessageHistory(BaseChatMessageHistory):
    def __init__(self, summary_memory: ConversationSummaryMemory):
        self.summary_memory = summary_memory

    @property
    def messages(self) -> list[BaseMessage]:
        if self.summary_memory.buffer:
            return [SystemMessage(content=self.summary_memory.buffer)]
        return []

    def add_message(self, message: BaseMessage) -> None:
        self.summary_memory.chat_memory.add_message(message)
        if len(self.summary_memory.chat_memory.messages) == 2:  # Після додавання human та ai
            self.summary_memory.buffer = self.summary_memory.predict_new_summary(
                self.summary_memory.chat_memory.messages,
                self.summary_memory.buffer
            )
            self.summary_memory.chat_memory.clear()
    
    def clear(self) -> None:
        self.summary_memory.buffer = ""
        self.summary_memory.chat_memory.clear()