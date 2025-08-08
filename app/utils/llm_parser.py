from langchain.prompts.chat import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain.output_parsers import PydanticOutputParser
from langchain_openai import ChatOpenAI
from langchain.schema import StrOutputParser
from langchain.schema.runnable import RunnablePassthrough
import json
import re
from typing import List, Optional
from models.llms.itinerary import ItineraryDay, TravelItinerary
import logging

logger = logging.getLogger(__name__)
class ItineraryParserTemplate:
    def __init__(self) -> None:
        self.system_instruction = """
        You are a travel planning expert who converts detailed travel descriptions into structured itineraries.
        
        The travel description will be provided between ## markers. Convert it into a structured day-by-day itinerary.
        
        Guidelines:
        - Break down the trip into daily plans
        - Include specific activities for each day
        - Identify the main location for each day
        - Determine the primary transportation method
        - If accommodation is mentioned, include it
        - Keep activities practical and realistic (max 10 per day)
        - Transportation options: "driving", "walking", "cycling", "public_transit", "flight", "mixed"
        
        Output ONLY clean JSON without markdown formatting or additional text.
        
        {format_instructions}
        """
        
        self.user_request = """
        ## {request} ##
        """
        
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
    def __init__(self, model="gpt-3.5-turbo", api_key=None, temp=0):
        if not api_key:
            raise ValueError("API key is required")
        
        self.model = ChatOpenAI(model=model, temperature=temp, openai_api_key=api_key)
        self.prompt = ItineraryParserTemplate()
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
            logger.info("JSON parsing failed, trying text parsing: {e}")
            return self._fallback_text_parsing(request, result)
            
        except Exception as e:
            raise ValueError(f"Failed to parse itinerary: {e}")
    
    def _clean_json_output(self, output: str) -> str:
        output = re.sub(r'^```json\s*', '', output.strip())
        output = re.sub(r'\s*```$', '', output.strip())
        
        json_match = re.search(r'\{.*\}', output, re.DOTALL)
        if json_match:
            return json_match.group(0)
        
        return output
