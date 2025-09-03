"""
This module provides functionality to convert travel itinerary text(or user input) into structured JSON format
and manage the creation of conversation history for travel planning sessions.

Core Components:
---------------
- DataToCreateItinerary: Dataclass for storing metadata about itinerary creation requests
- ProvideJsonItineraries: Main class for processing and converting itinerary data
- Role & MessageType: Enums defining the type of conversation participant and message format

Key Functionality:
-----------------
1. **Text to JSON Conversion**: Converts human-readable itinerary text into structured JSON
2. **Message Creation**: Generates user and assistant message structures for conversation history
3. **Data Validation**: Ensures itinerary data is properly formatted and complete
4. **File Management**: Saves processed itineraries to JSON files with proper formatting

Data Flow:
----------
Raw Itinerary Text → Parse & Validate → Convert to JSON → Create Message Structure → Return Structured Data

Usage Patterns:
--------------
1. **For User Messages**: Creates message objects with original request content
2. **For Assistant Messages**: Creates message objects with structured trip data (destination, duration, activities)
3. **Session Management**: Tracks user_id, session_id, and timestamps for conversation history

Limitations:
------------
- Assumes single user message and single assistant response per session
- Message IDs and timestamps are placeholders (should be generated dynamically in production)
- Session summary generation is basic and could be improved
- Error handling returns None for failed operations

Dependencies:
-------------
- app.utils.parser_functions: For itinerary parsing and validation
- langdetect: For language detection in messages
- Standard library: json, pathlib, logging, dataclasses, enum

Example Usage:
--------------
user_prompt = "Generate a 3-day itinerary for a family visiting Barcelona. They enjoy museums and outdoor activities."
user_data = DataToCreateItinerary(
    user_id="user_messag_id",
    session_id="user_session_id",
    started_at="2025-01-01T00:00:00+00:00",
    sender=Role.USER,
    message_type=MessageType.TEXT,
    timezone_offset="+03:00"
)
provide_json_itineraries = ProvideJsonItineraries()
user_json_itinerary = provide_json_itineraries.provide_dict_itinerary(user_prompt, user_data)
"""

import json
from pathlib import Path
from app.utils.parser_functions import validate_itinerary, export_to_json, parse_itinerary_output
from enum import Enum
from dataclasses import dataclass
import logging
from typing import Optional
import re
from datetime import datetime
logger = logging.getLogger(__name__)

from langdetect import detect

class Role(Enum):
    USER = "user"
    ASSISTANT = "assistant"

class MessageType(Enum):
    TEXT = "text"
    IMAGE = "image"

@dataclass
class DataToCreateItinerary:
    user_id: str
    session_id: str
    started_at: str
    timezone_offset: str

@dataclass
class Message:
    text: str
    sender: Role
    message_type: MessageType


class ProvideJsonItineraries:
    def __init__(self):
        self.messages = []

    def _get_json_itinerary(self, message: str) -> Optional[str]:
        """
        Provides a JSON itinerary for the given message.
        """
        try:
            itinerary_data = parse_itinerary_output(message)
            if validate_itinerary(itinerary_data):
                itinerary_json = export_to_json(itinerary_data)
                return itinerary_json
            else:
                logger.error(f"❌ Error in _get_json_itinerary: Invalid itinerary")
                return None
        except Exception as e:
            logger.error(f"❌ Unexpected Error in _get_json_itinerary: {e}")
            return None

    def convert_to_dict(self, text: str) -> Optional[str]:
        """
        Converts a string to a JSON object.
        """
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.error(f"❌ Error in convert_to_dict: Invalid JSON — {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Unexpected Error in convert_to_dict: {e}")
            return None

    def save_itinerary_from_text(self, json_text: str, filename: str = "itinerary.json") -> None:
        data = self.convert_to_dict(json_text)
        if data is None:
            logger.error(f"❌ Error in save_itinerary_from_text: Invalid JSON — {json_text}")
            return

        self.save_itinerary_from_dict(data, filename)
    
    def save_itinerary_from_dict(self, data: dict, filename: str = "itinerary.json") -> None:
        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            logger.info(f"✅ Successfully saved to {Path(filename).resolve()}")
        except json.JSONDecodeError as e:
            logger.error(f"❌ Error in save_itinerary_from_dict: Invalid JSON — {e}")
        except Exception as e:
            logger.error(f"❌ Unexpected Error in _get_language: {e}")

    def _get_language(self, text: str) -> Optional[str]:
        try:
            return detect(text)
        except Exception as e:
            logger.error(f"❌ Unexpected Error in _get_language: {e}")
            return None

    def _check_if_ISO_8601(self, timestamp_str: str) -> bool:
        """
        Checks if the string exactly matches the format: YYYY-MM-DDTHH:MM:SS+HH:MM
        """
        # Exact pattern for format "2025-08-26T18:25:00+03:00"
        exact_pattern = r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?\+\d{2}:\d{2}$'
        
        # Check by pattern
        if not re.match(exact_pattern, timestamp_str):
            return False
        
        # Additional check through datetime
        try:
            datetime.fromisoformat(timestamp_str)
            return True
        except ValueError:
            return False

    def _create_user_message(self, itinerary_dict: dict, message: Message, data_to_create_itinerary: DataToCreateItinerary) -> Optional[dict]:
        try:
            return {
                "message_id": itinerary_dict.get("metadata").get("request_id"),
                "sender": message.sender.value,
                "timestamp": self._local_to_iso(itinerary_dict.get("metadata").get("timestamp"), data_to_create_itinerary.timezone_offset),
                "content": itinerary_dict.get("metadata").get("original_request"),
                "metadata": {
                    "language": itinerary_dict.get("language"),
                    "message_type": message.message_type.value,
                }
            }
        except Exception as e:
            logger.error(f"❌ Unexpected Error in _create_user_message: {e}")
            return None

    def _create_assistant_message(self, itinerary_dict: dict, message: Message, data_to_create_itinerary: DataToCreateItinerary) -> Optional[dict]:
        try:
            return {
            "message_id": itinerary_dict.get("metadata").get("request_id"),
            "sender": message.sender.value,
            "timestamp": self._local_to_iso(itinerary_dict.get("metadata").get("timestamp"), data_to_create_itinerary.timezone_offset),
            "trip_data": {
                "destination": itinerary_dict.get("destination"),
                "duration_days": itinerary_dict.get("duration_days"),
                "transportation": itinerary_dict.get("transportation"),
                "itinerary": itinerary_dict.get("itinerary"),
            }
        }
        except Exception as e:
            logger.error(f"❌ Unexpected Error in _create_assistant_message: {e}")
            return None
    
    def _validate_data_to_create_itinerary(self, data_to_create_itinerary: DataToCreateItinerary) -> bool:
        if not self._check_if_ISO_8601(data_to_create_itinerary.started_at):
            logger.error(f"❌ Error in _validate_data_to_create_itinerary: Invalid started_at timestamp")
            return False
        for key, value in data_to_create_itinerary.__dict__.items():
            if value is None:
                logger.error(f"❌ Error in _validate_data_to_create_itinerary: {key} is None")
                return False
        return True

    def _validate_message(self, message: Message) -> bool:
        if message.sender not in [Role.USER, Role.ASSISTANT]:
            logger.error(f"❌ Error in _validate_message: Invalid sender")
            return False
        if message.message_type not in [MessageType.TEXT, MessageType.IMAGE]:
            logger.error(f"❌ Error in _validate_message: Invalid message_type")
            return False
        return True

    def _local_to_iso(self, local_time_string: str, timezone_offset: str) -> Optional[str]:
        """Convert local format Python to ISO 8601 with timezone"""
        try:
            dt = datetime.strptime(local_time_string, "%Y-%m-%d %H:%M:%S.%f")
            iso_without_tz = dt.isoformat()
            return iso_without_tz + timezone_offset
        except Exception as e:
            logger.error(f"❌ Unexpected Error in _local_to_iso_with_timezone: {e}")
            return None

    def provide_dict_itinerary(self, messages: list[Message], data_to_create_itinerary: DataToCreateItinerary) -> Optional[dict]:
        """
        Constructs a session dictionary containing user and assistant messages, 
        including itinerary data, for downstream processing or storage.

        Limitations:
            - This implementation assumes only a single user message and a single assistant response.
            - Message IDs and timestamps are placeholders and should be generated dynamically in production.
            - Session summary is not generated from the input and should be improved for real use cases.

        Future improvements:
            - Integrate with a message ID and timestamp generator.
            - Generate session summary from conversation context or user input.
            - Support for multiple message turns and richer metadata.
        """
        if not self._check_if_ISO_8601(data_to_create_itinerary.started_at):
            logger.error(f"❌ Error in provide_dict_itinerary: Invalid started_at timestamp")
            return None

        entire_content = []
        session_summary = None
        for message in messages:
            itinerary_json_text = self._get_json_itinerary(message.text)
            itinerary_dict = self.convert_to_dict(itinerary_json_text)
            if session_summary is None:
                session_summary = itinerary_dict.get("session_summary")
            if itinerary_dict is None:
                logger.error(f"❌ Error in provide_dict_itinerary: Invalid itinerary json text")
                return None

            content = None

            if message.sender == Role.USER:
                content = self._create_user_message(itinerary_dict, message, data_to_create_itinerary)
                if content is None:
                    logger.error(f"❌ Error in provide_dict_itinerary: Invalid user message")
                    return None
            else:
                content = self._create_assistant_message(itinerary_dict, message, data_to_create_itinerary)
                if content is None:
                    logger.error(f"❌ Error in provide_dict_itinerary: Invalid assistant message")
                    return None

            entire_content.append(content)

        try:
            result = {
                "user_id": getattr(data_to_create_itinerary, "user_id"), #Partition key
                "session_id": getattr(data_to_create_itinerary, "session_id"), #Sort key
                "session_summary": session_summary,
                "started_at": getattr(data_to_create_itinerary, "started_at"),
                "messages": entire_content
            }
            if not self._check_if_ISO_8601(result['messages'][0]['timestamp']):
                logger.error(f"❌ Error in provide_dict_itinerary: Invalid timestamp")
                return None
            return result

        except Exception as e:
            logger.error(f"❌ Unexpected Error in provide_dict_itinerary: {e}")
            return None

    def provide_json_itinerary(self, messages: list[Message], data_to_create_itinerary: DataToCreateItinerary) -> Optional[str]:
        if not self._validate_data_to_create_itinerary(data_to_create_itinerary):
            logger.error(f"❌ Error in provide_json_itinerary: Invalid data_to_create_itinerary")
            return None
        for message in messages:
            if not self._validate_message(message):
                logger.error(f"❌ Error in provide_json_itinerary: Invalid message")
                return None
        itinerary_dict = self.provide_dict_itinerary(messages, data_to_create_itinerary)
        if itinerary_dict is None:
            return None
        try:
            return json.dumps(itinerary_dict)
        except Exception as e:
            logger.error(f"❌ Unexpected Error in provide_json_itinerary: {e}")
            return None