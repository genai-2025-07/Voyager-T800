from langchain.prompts.chat import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain.output_parsers import PydanticOutputParser
from langchain_openai import ChatOpenAI
from langchain.schema import StrOutputParser
from langchain.schema.runnable import RunnablePassthrough
import json
import re
import os
from pathlib import Path
from typing import List, Optional
from app.models.llms.itinerary import ItineraryDay, TravelItinerary, RequestMetadata
from app.utils.read_prompt_from_file import load_prompt_from_file  
import logging
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class ItineraryParserTemplate:
    """Template for creating itinerary parsing prompts"""
    
    def __init__(self, prompt_file: str = None) -> None:
        """
        Initialize the parser template.
        
        Args:
            prompt_file: Path to the prompt file. If None, uses default path.
        """
        if prompt_file is None:
            prompt_file = Path("app") / "prompts" / "itinerary_parser.txt"
        else:
            prompt_file = Path(prompt_file)   
        self.system_instruction = load_prompt_from_file(str(prompt_file))
        self.user_request = "## {request} ##"  
        
        class SimpleTravelItinerary(BaseModel):
            """Simplified model for LLM output parsing"""
            destination: str
            duration_days: int
            transportation: str
            itinerary: List[ItineraryDay]
            language: str  # AI should detect this
            session_summary: str   # AI should generate this
        
        self.parser = PydanticOutputParser(pydantic_object=SimpleTravelItinerary)
        self.system_message = SystemMessagePromptTemplate.from_template(
            self.system_instruction,
            partial_variables={'format_instructions': self.parser.get_format_instructions()}
        )
        self.user_message = HumanMessagePromptTemplate.from_template(
            self.user_request, 
            input_variables=['request']
        )
        self.prompt_template = ChatPromptTemplate.from_messages([
            self.system_message, 
            self.user_message
        ])

class ItineraryParserAgent:
    """
    AI-powered itinerary parser using OpenAI LLM.
    
    Environment Variables:
        OPENAI_API_KEY: Required OpenAI API key
        OPENAI_MODEL: Model name (default: gpt-3.5-turbo)
        OPENAI_TEMPERATURE: Temperature setting (default: 0)
    """
    
    def __init__(self, model=None, temp=None, prompt_file: str = None, api_key: str = None):
        """
        Initialize the parser agent.
        
        Args:
            model: OpenAI model name
            temp: Temperature setting
            prompt_file: Path to custom prompt file
            api_key: OpenAI API key (for testing)
        """
        api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        
        if model is None:
            model = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
        
        if temp is None:
            temp = float(os.getenv("OPENAI_TEMPERATURE", "0"))
        
        try:
            self.model = ChatOpenAI(
                model=model,
                temperature=temp,
                openai_api_key=api_key
            )
        except Exception as e:
            logger.error(f"Failed to initialize ChatOpenAI model: {e}")
            raise ValueError(f"Failed to initialize OpenAI model '{model}': {e}")
            
        self.prompt = ItineraryParserTemplate(prompt_file)
        self.chain = (
            RunnablePassthrough() 
            | self.prompt.prompt_template 
            | self.model 
            | StrOutputParser()
        )
    
    def parse_itinerary_output(self, request: str) -> TravelItinerary:
        """
        Parse itinerary from natural language request.
        
        Args:
            request: Natural language travel itinerary request
            
        Returns:
            TravelItinerary: Parsed and validated travel itinerary
            
        Raises:
            ValueError: If parsing fails or input is invalid
        """
        if not request or not request.strip():
            raise ValueError("Request cannot be empty")
            
        try:
            logger.debug(f"Processing request: {request[:100]}...")
            
            result = self.chain.invoke({
                'request': request, 
                'format_instructions': self.prompt.parser.get_format_instructions()
            })
            
            logger.debug(f"Raw LLM result: {result[:200]}...")
            
            cleaned_result = self._clean_json_output(result)
            logger.debug(f"Cleaned result: {cleaned_result[:200]}...")
            
            try:
                parsed_data = json.loads(cleaned_result)
            except json.JSONDecodeError as e:
                logger.error(f"JSON parsing failed for: {cleaned_result[:100]}...")
                raise ValueError(f"Failed to parse JSON response: {e}")
            
            metadata = RequestMetadata(
                original_request=request,
                parser_used='ai'
            )
            
            parsed_data['metadata'] = metadata.dict()
            
            itinerary = TravelItinerary(**parsed_data)
            
            return itinerary
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing failed: {e}")
            raise ValueError(f"Failed to parse JSON response: {e}")
            
        except Exception as e:
            logger.error(f"Failed to parse itinerary: {e}")
            raise ValueError(f"Failed to parse itinerary: {e}")
    
    def _clean_json_output(self, output: str) -> str:
        """
        Clean LLM output to extract valid JSON.
        
        Args:
            output: Raw LLM output string
            
        Returns:
            str: Cleaned JSON string
        """
        output = output.strip()
        
        # Remove markdown code blocks
        output = re.sub(r'^```(?:json)?\s*', '', output)
        output = re.sub(r'\s*```$', '', output)
        
        # Try to extract JSON object more carefully
        # Look for the main JSON structure
        brace_count = 0
        start_idx = -1
        
        for i, char in enumerate(output):
            if char == '{':
                if start_idx == -1:
                    start_idx = i
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0 and start_idx != -1:
                    return output[start_idx:i+1]
        
        # Fallback to original regex method
        json_match = re.search(r'\{.*\}', output, re.DOTALL)
        if json_match:
            return json_match.group(0)
        
        return output