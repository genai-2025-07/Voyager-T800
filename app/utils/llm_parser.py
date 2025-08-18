from langchain.prompts.chat import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain.output_parsers import PydanticOutputParser
from langchain_openai import ChatOpenAI
from langchain.schema import StrOutputParser
from langchain.schema.runnable import RunnablePassthrough
import json
import re
import os
from typing import List, Optional
from app.models.llms.itinerary import ItineraryDay, TravelItinerary
from app.utils.read_prompt_from_file import load_prompt_from_file  
import logging

logger = logging.getLogger(__name__)

class ItineraryParserTemplate:
    def __init__(self, prompt_file: str = None) -> None:
        if prompt_file is None:
            prompt_file = os.path.join("app", "prompts", "itinerary_parser.txt")
            
        self.system_instruction = load_prompt_from_file(prompt_file)
        self.user_request = "## {request} ##"  
        
        self.parser = PydanticOutputParser(pydantic_object=TravelItinerary)
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
    def __init__(self, model=None, temp=None, prompt_file: str = None):
        
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY environment variable is required"
            )
        
        if model is None:
            model = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
        
        if temp is None:
            temp = float(os.getenv("OPENAI_TEMPERATURE", "0"))
        
        self.model = ChatOpenAI(
            model=model,
            temperature=temp,
            openai_api_key=api_key
        )
        self.prompt = ItineraryParserTemplate(prompt_file)
        self.chain = (
            RunnablePassthrough() 
            | self.prompt.prompt_template 
            | self.model 
            | StrOutputParser()
        )
    
    def parse_itinerary_output(self, request: str) -> TravelItinerary:
        try:
            result = self.chain.invoke({
                'request': request, 
                'format_instructions': self.prompt.parser.get_format_instructions()
            })
            
            cleaned_result = self._clean_json_output(result)
            parsed_data = json.loads(cleaned_result)
            itinerary = TravelItinerary(**parsed_data)
            
            return itinerary
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing failed: {e}")
            raise ValueError(f"Failed to parse JSON response: {e}")
            
        except Exception as e:
            logger.error(f"Failed to parse itinerary: {e}")
            raise ValueError(f"Failed to parse itinerary: {e}")
    
    def _clean_json_output(self, output: str) -> str:
        output = re.sub(r'^```json\s*', '', output.strip())
        output = re.sub(r'\s*```$', '', output.strip())
        
        json_match = re.search(r'\{.*\}', output, re.DOTALL)
        if json_match:
            return json_match.group(0)
        
        return output