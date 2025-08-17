import pytest
import logging
from unittest.mock import Mock
from app.memory.custom_summary_memory import SummaryChatMessageHistory
from langchain.memory import ConversationSummaryMemory
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from langchain_core.language_models import BaseLanguageModel
from langchain_core.outputs import LLMResult, Generation
from langchain_core.prompt_values import StringPromptValue

# Налаштування логування для дебагінгу тестів
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(message)s")

# Мок для BaseLanguageModel
class MockLLM(BaseLanguageModel):
    def __init__(self):
        super().__init__()
        self._predict = Mock(return_value="Summarized conversation")

    def predict(self, text: str, *, stop: list[str] | None = None) -> str:
        logging.debug(f"Predict called with text: {text}")
        return self._predict(text)

    def predict_messages(self, messages: list[BaseMessage], *, stop: list[str] | None = None) -> BaseMessage:
        logging.debug(f"Predict_messages called with messages: {messages}")
        return SystemMessage(content=self._predict(str(messages)))

    def generate_prompt(self, prompts: list[StringPromptValue], stop: list[str] | None = None, callbacks: list | None = None, **kwargs) -> LLMResult:
        logging.debug(f"Generate_prompt called with prompts: {prompts}, kwargs: {kwargs}")
        return LLMResult(generations=[[Generation(text=self._predict(str(prompts)))]])
    
    async def agenerate_prompt(self, prompts: list[StringPromptValue], stop: list[str] | None = None, callbacks: list | None = None, **kwargs) -> LLMResult:
        logging.debug(f"Agenerate_prompt called with prompts: {prompts}, kwargs: {kwargs}")
        return LLMResult(generations=[[Generation(text=self._predict(str(prompts)))]])
    
    async def apredict(self, text: str, *, stop: list[str] | None = None) -> str:
        logging.debug(f"Apredict called with text: {text}")
        return self._predict(text)
    
    async def apredict_messages(self, messages: list[BaseMessage], *, stop: list[str] | None = None) -> BaseMessage:
        logging.debug(f"Apredict_messages called with messages: {messages}")
        return SystemMessage(content=self._predict(str(messages)))

    def invoke(self, *args, **kwargs):
        logging.debug(f"Invoke called with args: {args}, kwargs: {kwargs}")
        return self.predict(*args, **kwargs)

    def __call__(self, *args, **kwargs):
        logging.debug(f"__call__ called with args: {args}, kwargs: {kwargs}")
        return self.predict(*args, **kwargs)

@pytest.fixture
def mock_llm():
    return MockLLM()

@pytest.fixture
def summary_memory(mock_llm):
    return ConversationSummaryMemory(llm=mock_llm)

@pytest.fixture
def chat_history(summary_memory):
    return SummaryChatMessageHistory(summary_memory=summary_memory)

def test_init_invalid_memory():
    with pytest.raises(TypeError):
        SummaryChatMessageHistory(summary_memory="not_a_memory")

def test_empty_messages(chat_history):
    assert chat_history.messages == []

def test_add_single_message(chat_history):
    message = HumanMessage(content="Hello")
    chat_history.add_message(message)
    # With default trigger_count=2, single message shouldn't trigger summary
    assert len(chat_history.summary_memory.chat_memory.messages) == 1
    assert chat_history.messages == []

def test_add_invalid_message(chat_history):
    with pytest.raises(TypeError):
        chat_history.add_message("not_a_message")

def test_summary_trigger(chat_history, mock_llm):
    # Add messages up to trigger count
    chat_history.add_message(HumanMessage(content="Hello"))
    chat_history.add_message(AIMessage(content="Hi there"))
    
    # Verify summary was created
    assert len(chat_history.messages) == 1, f"Expected 1 message, got {len(chat_history.messages)}"
    assert isinstance(chat_history.messages[0], SystemMessage)
    assert chat_history.messages[0].content == "Summarized conversation"

def test_clear_memory(chat_history):
    # Add some messages
    chat_history.add_message(HumanMessage(content="Hello"))
    chat_history.summary_memory.buffer = "Previous summary"
    
    # Clear memory
    chat_history.clear()
    
    # Verify everything is cleared
    assert chat_history.messages == []
    assert chat_history.summary_memory.buffer == ""
    assert len(chat_history.summary_memory.chat_memory.messages) == 0

def test_custom_trigger_count(mock_llm):
    summary_memory = ConversationSummaryMemory(llm=mock_llm)
    chat_history = SummaryChatMessageHistory(
        summary_memory=summary_memory,
        summary_trigger_count=3
    )
    
    # Add messages
    chat_history.add_message(HumanMessage(content="Hello"))
    chat_history.add_message(AIMessage(content="Hi"))
    assert len(chat_history.summary_memory.chat_memory.messages) == 2
    
    # Third message should trigger summary
    chat_history.add_message(HumanMessage(content="How are you?"))
    assert len(chat_history.messages) == 1

def test_failed_summary(chat_history, mock_llm):
    mock_llm._predict.side_effect = Exception("Summary failed")
    
    # Add messages up to trigger
    chat_history.add_message(HumanMessage(content="Hello"))
    chat_history.add_message(AIMessage(content="Hi"))
    
    # Messages should still be in memory since summary failed
    assert len(chat_history.summary_memory.chat_memory.messages) == 2
    assert chat_history.messages == []

def test_incremental_summaries(chat_history, mock_llm):
    # Setting up mock to return different summaries for each call
    mock_llm._predict.side_effect = ["First summary", "Second summary"]
    
    # First cycle
    chat_history.add_message(HumanMessage(content="Hello"))
    chat_history.add_message(AIMessage(content="Hi"))
    assert len(chat_history.messages) == 1, f"Expected 1 message, got {len(chat_history.messages)}"
    first_summary = chat_history.messages[0].content
    
    # Second cycle
    chat_history.add_message(HumanMessage(content="How are you?"))
    chat_history.add_message(AIMessage(content="I'm good!"))
    assert len(chat_history.messages) == 1, f"Expected 1 message, got {len(chat_history.messages)}"
    second_summary = chat_history.messages[0].content
    
    assert first_summary == "First summary"
    assert second_summary == "Second summary"