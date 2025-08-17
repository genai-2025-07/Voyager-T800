import logging
from langchain_core.messages import BaseMessage, SystemMessage
from langchain_core.chat_history import BaseChatMessageHistory
from langchain.memory import ConversationSummaryMemory

# Configure logging for this module if not already configured
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

class SummaryChatMessageHistory(BaseChatMessageHistory):
    """
    A chat message history manager that summarizes conversations after a specified number of messages.
    This class wraps a ConversationSummaryMemory instance and accumulates messages until a trigger count is reached.
    Once the trigger count is met, it summarizes the accumulated messages and stores the summary in a buffer,
    clearing the chat memory for the next batch. This approach is useful for managing long conversations
    by keeping a running summary instead of storing all messages.
        Initialize the SummaryChatMessageHistory.
            summary_memory (ConversationSummaryMemory): The memory instance used to store and summarize messages.
            summary_trigger_count (int, optional): Number of messages to accumulate before updating the summary.
                Defaults to 2. Increase this value for longer interactions before summarization.
        Raises:
            TypeError: If summary_memory is not an instance of ConversationSummaryMemory.
        Get the current summarized messages.
        Returns:
            list[BaseMessage]: A list containing a single SystemMessage with the current summary buffer,
                or an empty list if the buffer is empty.
        Add a new message to the chat memory and update the summary if the trigger count is reached.
            message (BaseMessage): The message to add.
        Raises:
            TypeError: If message is not an instance of BaseMessage or its subclass.
        Side Effects:
            Updates the summary buffer and clears chat memory when the trigger count is met.
            Prints an error message if summarization fails.
        Clear the summary buffer and chat memory.
        Resets both the summary buffer and the underlying chat memory to an empty state.
    """
    def __init__(self, summary_memory: ConversationSummaryMemory, summary_trigger_count: int = 2):
        """
        Args:
            summary_memory: The ConversationSummaryMemory instance to use.
            summary_trigger_count: Number of messages to accumulate before updating the summary.
                Defaults to 2, which assumes strict alternation of human and AI messages.
                Increase this value if your interactions involve more messages before summarization.
        """
        if not isinstance(summary_memory, ConversationSummaryMemory):
            raise TypeError("summary_memory must be a ConversationSummaryMemory instance")
        self.summary_memory = summary_memory
        self.summary_trigger_count = summary_trigger_count

    @property
    def messages(self) -> list[BaseMessage]:
        """
        Returns a list of BaseMessage objects representing the current summary memory.

        If the summary memory buffer contains data, the method returns a list with a single SystemMessage
        whose content is the buffer's contents. If the buffer is empty, it returns an empty list.

        Returns:
            list[BaseMessage]: A list containing a SystemMessage if the buffer is not empty, otherwise an empty list.
        """
        if self.summary_memory.buffer:
            return [SystemMessage(content=self.summary_memory.buffer)]
        return []

    def add_message(self, message: BaseMessage) -> None:
        """
        Adds a message to the chat memory and triggers summarization when the message count reaches the specified threshold.

        Args:
            message (BaseMessage): The message object to be added. Must be an instance of BaseMessage or its subclass.

        Raises:
            TypeError: If the provided message is not an instance of BaseMessage or its subclass.

        Behavior:
            - Adds the given message to the chat memory.
            - When the number of messages in the chat memory reaches the summary trigger count, attempts to update the summary buffer by summarizing the new messages.
            - If summarization is successful, updates the summary buffer and clears the chat memory.
            - If an error occurs during summarization, logs the exception without clearing the chat memory.
        """
        if not isinstance(message, BaseMessage):
            raise TypeError("message must be an instance of BaseMessage or its subclass")
        self.summary_memory.chat_memory.add_message(message)
        # Summarize when the number of messages reaches the trigger count.
        # To update the summary we need the last 2 messages(human and AI).
        if len(self.summary_memory.chat_memory.messages) == self.summary_trigger_count:
            try:
                # Pass only the new messages for incremental summary update
                new_messages = self.summary_memory.chat_memory.messages
                updated_buffer = self.summary_memory.predict_new_summary(
                    new_messages,
                    self.summary_memory.buffer
                )
                # Only update the buffer and clear messages if summarization succeeded.
                self.summary_memory.buffer = updated_buffer
                logging.info("Summary buffer updated successfully.")
                # It is now safe to clear the chat memory because all messages have been summarized into the buffer.
                self.summary_memory.chat_memory.clear()
                logging.info("Chat memory cleared after summary update.")
            except Exception as e:
                logging.error(f"Error updating summary: {e}")
    
    def clear(self) -> None:
        """
        Clears the summary memory by resetting the buffer and removing all chat history.

        This method sets the summary buffer to an empty string and clears the chat memory,
        effectively removing all stored conversation data and summaries.
        """
        self.summary_memory.buffer = ""
        self.summary_memory.chat_memory.clear()
        logging.info("Summary buffer and chat memory cleared.")