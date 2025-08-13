#!/usr/bin/env python3
import os
import json
from typing import Dict, List, Optional, Any

from openai import OpenAI
from app.config.logging_config import get_logger

logger = get_logger("voyager_t800.llm_parser")


class LLMParser:
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4-turbo-preview", temperature: float = 0.1):
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OpenAI API key is required. Set OPENAI_API_KEY environment variable or pass it to constructor.")
        
        self.client = OpenAI(api_key=self.api_key)
        self.model = model
        self.temperature = temperature
        logger.info(f"LLMParser initialized with model={model}")
    
    def parse_itinerary_to_json(self, itinerary_text: str) -> Optional[List[Dict[str, Any]]]:
        try:
            prompt = self._create_parsing_prompt(itinerary_text)
            
            logger.info("Using LLM to parse itinerary structure")
            llm_response = self._query_llm(prompt)
            
            days_data = self._extract_json_from_response(llm_response)
            
            if days_data and isinstance(days_data, list):
                logger.info(f"Successfully parsed {len(days_data)} days from itinerary using JSON")
                return days_data
            else:
                logger.warning("JSON parsing failed, attempting text-based extraction")
                days_data = self._extract_structured_data_from_text(llm_response)
                
                if days_data and isinstance(days_data, list):
                    logger.info(f"Successfully parsed {len(days_data)} days from itinerary using text extraction")
                    return days_data
                else:
                    logger.warning("Both JSON and text parsing failed")
                    return None
                
        except Exception as e:
            logger.error(f"LLM parsing failed: {e}")
            return None
    
    def _load_prompt_template(self, template_name: str) -> str:
        try:
            template_path = os.path.join(os.path.dirname(__file__), f"{template_name}.txt")
            with open(template_path, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except FileNotFoundError as e:
            logger.error(f"Prompt template file not found: {template_name}.txt")
            raise RuntimeError(f"Prompt template file not found: {template_name}.txt")
        except PermissionError as e:
            logger.error(f"Permission denied accessing prompt template: {template_name}.txt")
            raise RuntimeError(f"Permission denied accessing prompt template: {template_name}.txt")
        except UnicodeDecodeError as e:
            logger.error(f"Failed to decode prompt template {template_name}.txt: {e}")
            raise RuntimeError(f"Failed to decode prompt template {template_name}.txt: {e}")
        except OSError as e:
            logger.error(f"OS error loading prompt template {template_name}: {e}")
            raise RuntimeError(f"OS error loading prompt template {template_name}: {e}")

    def _create_parsing_prompt(self, itinerary_text: str) -> str:
        template = self._load_prompt_template("parsing_prompt")
        return template + itinerary_text
    
    def _query_llm(self, prompt: str) -> str:
        try:
            # Here we can experiment with the model parameters to make its responses more stable.
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a travel itinerary parser. Extract structured information and return only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=2000,
                temperature=self.temperature,
            )
            
            itinerary = response.choices[0].message.content.strip()
            
            if response.usage is not None:
                tokens_used = response.usage.total_tokens
                logger.info(f"Itinerary parsed successfully using {tokens_used} tokens")
            else:
                logger.warning("Response usage information not available")
            
            return itinerary
            
        except Exception as e:
            logger.error(f"LLM query failed: {e}")
            raise RuntimeError(f"LLM query failed: {e}")
    
    def _extract_json_from_response(self, llm_response: str) -> Optional[List[Dict[str, Any]]]:
        try:
            response_clean = llm_response.strip()
            
            start_idx = response_clean.find('{')
            end_idx = response_clean.rfind('}') + 1
            
            if start_idx != -1 and end_idx > start_idx:
                json_str = response_clean[start_idx:end_idx]
                parsed_data = json.loads(json_str)
                
                if isinstance(parsed_data, dict) and 'days' in parsed_data:
                    return parsed_data['days']
                elif isinstance(parsed_data, list):
                    return parsed_data
                else:
                    logger.warning("LLM response doesn't contain expected 'days' structure")
                    return None
            else:
                logger.warning("No JSON object found in LLM response")
                return None
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from LLM response: {e}")
            return None
        except Exception as e:
            logger.error(f"Error extracting JSON from LLM response: {e}")
            return None
    
    def _extract_structured_data_from_text(self, llm_response: str) -> Optional[List[Dict[str, Any]]]:
        try:
            days_data = []
            lines = llm_response.split('\n')
            current_day = None
            current_city = "Unknown"
            current_activities = []
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                day_match = self._extract_day_info(line)
                if day_match:
                    if current_day is not None:
                        days_data.append({
                            "day": current_day,
                            "city": current_city,
                            "activities": current_activities.copy()
                        })
                    
                    current_day = day_match["day"]
                    current_city = day_match.get("city", "Unknown")
                    current_activities = []
                    continue
                
                city_match = self._extract_city_info(line)
                if city_match and current_day is not None:
                    current_city = city_match
                    continue
                
                activity = self._extract_activity_info(line)
                if activity and current_day is not None:
                    current_activities.append(activity)
                    continue
            
            if current_day is not None:
                days_data.append({
                    "day": current_day,
                    "city": current_city,
                    "activities": current_activities
                })
            
            if not days_data:
                all_activities = self._extract_all_activities(llm_response)
                if all_activities:
                    days_data = [{
                        "day": 1,
                        "city": "Unknown",
                        "activities": all_activities
                    }]
            
            if days_data:
                logger.info(f"Successfully extracted {len(days_data)} days from text response")
                return days_data
            else:
                logger.warning("No structured data found in text response")
                return None
                
        except Exception as e:
            logger.error(f"Error extracting structured data from text: {e}")
            return None
    
    def _extract_day_info(self, line: str) -> Optional[Dict[str, Any]]:
        import re
        
        patterns = [
            r'day\s+(\d+)',  # "day 1", "day 2"
            r'day\s+(\d+)\s+in\s+([^,\n]+)',  # "day 1 in Kyiv"
            r'day\s+(\d+):\s*([^,\n]+)',  # "day 1: Kyiv"
            r'(\d+)\s*:\s*([^,\n]+)',  # "1: Kyiv"
        ]
        
        line_lower = line.lower()
        
        for pattern in patterns:
            match = re.search(pattern, line_lower)
            if match:
                day_num = int(match.group(1))
                city = match.group(2).strip() if len(match.groups()) > 1 else "Unknown"
                return {"day": day_num, "city": city}
        
        return None
    
    def _extract_city_info(self, line: str) -> Optional[str]:
        import re
        
        city_patterns = [
            r'in\s+([^,\n]+)',  # "in Kyiv"
            r'city:\s*([^,\n]+)',  # "city: Kyiv"
            r'location:\s*([^,\n]+)',  # "location: Kyiv"
        ]
        
        line_lower = line.lower()
        
        for pattern in city_patterns:
            match = re.search(pattern, line_lower)
            if match:
                city = match.group(1).strip()
                # Filter out common non-city words
                if city and len(city) > 2 and city not in ['the', 'and', 'or', 'with']:
                    return city
        
        return None
    
    def _extract_all_activities(self, text: str) -> List[str]:
        activities = []
        lines = text.split('\n')
        
        for line in lines:
            activity = self._extract_activity_info(line)
            if activity:
                activities.append(activity)
        
        return activities

    def _extract_activity_info(self, line: str) -> Optional[str]:
        import re
        
        line_clean = line.strip()
        
        line_clean = re.sub(r'^[-•*]\s*', '', line_clean)
        line_clean = re.sub(r'^\d+\.\s*', '', line_clean)
        line_clean = re.sub(r'^[a-z]\)\s*', '', line_clean)
        
        if (len(line_clean) > 5 and 
            not line_clean.lower().startswith(('day', 'city', 'location', 'activities')) and
            not re.match(r'^[A-Z\s]+$', line_clean)):
            return line_clean
        
        return None
