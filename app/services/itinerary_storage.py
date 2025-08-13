#!/usr/bin/env python3
import json
import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

from app.config.logging_config import get_logger
from .llm_parser import LLMParser

logger = get_logger("voyager_t800.itinerary_storage")


class ItineraryStorage:
    def __init__(self, storage_dir: Optional[str] = None):
        self.storage_dir = storage_dir or os.getenv('ITINERARY_STORAGE_DIR')
        if not self.storage_dir:
            raise ValueError("ITINERARY_STORAGE_DIR environment variable is not set. Please add it to your .env file.")
        self._ensure_storage_dir()
        self.llm_parser = LLMParser()
        logger.info(f"ItineraryStorage initialized with storage directory: {self.storage_dir}")
    
    def _ensure_storage_dir(self) -> None:
        try:
            Path(self.storage_dir).mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create storage directory {self.storage_dir}: {e}")
            raise RuntimeError(f"Failed to create storage directory: {e}")
    
    # Creates a random Universally Unique Identifier
    def _generate_session_id(self) -> str:
        return f"session_{uuid.uuid4().hex[:8]}"
    
    def _parse_itinerary_with_llm(self, itinerary_text: str) -> List[Dict[str, Any]]:
        try:
            logger.info("Using LLM to parse itinerary structure")
            days_data = self.llm_parser.parse_itinerary_to_json(itinerary_text)
            
            if days_data and isinstance(days_data, list):
                logger.info(f"Successfully parsed {len(days_data)} days from itinerary")
                return days_data
            else:
                logger.warning("LLM parsing failed, falling back to basic parsing")
                raise RuntimeError("LLM parsing failed, falling back to basic parsing")
                
        except Exception as e:
            logger.error(f"LLM parsing failed: {e}, falling back to basic parsing")
            raise RuntimeError(f"LLM parsing failed: {e}, falling back to basic parsing")
    
    def _extract_json_from_llm_response(self, llm_response: str) -> Optional[List[Dict[str, Any]]]:
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
    
    def _extract_activities_from_itinerary(self, itinerary_text: str) -> List[str]:
        activities = []
        lines = itinerary_text.split('\n')
        
        for line in lines:
            line = line.strip()
            if (line.startswith('- ') or 
                line.startswith('• ') or 
                line.startswith('* ') or
                line.startswith('1.') or
                line.startswith('2.') or
                line.startswith('3.') or
                line.startswith('4.') or
                line.startswith('5.')):
                activity = line.lstrip('- •*123456789. ').strip()
                if activity and len(activity) > 5:
                    activities.append(activity)
        
        return activities
    
    def create_itinerary_json(self, user_input: str, itinerary_text: str, preferences: Dict[str, str], session_id: Optional[str] = None) -> Dict[str, Any]:
        session_id = session_id or self._generate_session_id()
        
        destinations = []
        if preferences.get('destination'):
            dest = preferences['destination']
            if ' and ' in dest:
                destinations = [d.strip() for d in dest.split(' and ')]
            elif ', and ' in dest:
                destinations = [d.strip() for d in dest.split(', and ')]
            else:
                destinations = [dest]
        
        interests = []
        if preferences.get('interests'):
            interests = [interest.strip() for interest in preferences['interests'].split(',')]
        
        # Use LLM to parse the itinerary structure
        days = self._parse_itinerary_with_llm(itinerary_text)
        
        itinerary_data = {
            "user_id": session_id,
            "timestamp": datetime.now().isoformat(),
            "user_request": user_input,
            "trip_duration": preferences.get('duration', '1 day'),
            "destinations": destinations,
            "preferences": interests,
            "budget": preferences.get('budget', 'Unknown'),
            "travel_style": preferences.get('travel_style', 'Unknown'),
            "days": days,
            "raw_itinerary": itinerary_text
        }
        
        logger.info(f"Created itinerary JSON for session {session_id}")
        return itinerary_data
    
    def _serialize_for_json(self, obj: Any) -> Any:
        if hasattr(obj, 'value'):
            return obj.value
        elif hasattr(obj, '__dict__'):
            return str(obj)
        else:
            return obj
    
    def _prepare_data_for_json(self, data: Any) -> Any:
        if isinstance(data, dict):
            return {key: self._prepare_data_for_json(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [self._prepare_data_for_json(item) for item in data]
        else:
            return self._serialize_for_json(data)
    
    def save_itinerary(self, itinerary_data: Dict[str, Any], filename: Optional[str] = None) -> str:
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            session_id = itinerary_data.get('user_id', 'unknown')
            filename = f"itinerary_{session_id}_{timestamp}.json"
        
        filepath = os.path.join(self.storage_dir, filename)
        
        try:
            json_ready_data = self._prepare_data_for_json(itinerary_data)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                # Added options for writing non-Latin characters and for beautiful indentation
                json.dump(json_ready_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Itinerary saved to {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Failed to save itinerary to {filepath}: {e}")
            raise RuntimeError(f"Failed to save itinerary: {e}")
    
    def load_itinerary(self, filepath: str) -> Dict[str, Any]:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                itinerary_data = json.load(f)
            
            logger.info(f"Itinerary loaded from {filepath}")
            return itinerary_data
            
        except FileNotFoundError:
            logger.error(f"Itinerary file not found: {filepath}")
            raise FileNotFoundError(f"Itinerary file not found: {filepath}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in itinerary file {filepath}: {e}")
            raise ValueError(f"Invalid JSON in itinerary file: {e}")
        except Exception as e:
            logger.error(f"Failed to load itinerary from {filepath}: {e}")
            raise RuntimeError(f"Failed to load itinerary: {e}")
    
    def list_itineraries(self) -> List[str]:
        try:
            files = []
            for file in Path(self.storage_dir).glob("itinerary_*.json"):
                files.append(str(file))
            
            logger.info(f"Found {len(files)} itinerary files")
            return sorted(files)
            
        except Exception as e:
            logger.error(f"Failed to list itineraries: {e}")
            return []
    
    def delete_itinerary(self, filepath: str) -> bool:
        try:
            os.remove(filepath)
            logger.info(f"Itinerary deleted: {filepath}")
            return True
            
        except FileNotFoundError:
            logger.warning(f"Itinerary file not found for deletion: {filepath}")
            return False
        except Exception as e:
            logger.error(f"Failed to delete itinerary {filepath}: {e}")
            return False
    
    def get_itinerary_as_json_string(self, itinerary_data: Dict[str, Any]) -> str:

        try:
            return json.dumps(itinerary_data, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to convert itinerary to JSON string: {e}")
            raise RuntimeError(f"Failed to convert itinerary to JSON: {e}")
    
    def find_itinerary_by_session(self, session_id: str) -> Optional[str]:
        try:
            for file in Path(self.storage_dir).glob(f"itinerary_{session_id}_*.json"):
                return str(file)
            return None
            
        except Exception as e:
            logger.error(f"Failed to search for session {session_id}: {e}")
            return None


# TODO: When the database is created - implement saving history in the database
