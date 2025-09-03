#!/usr/bin/env python3
# Standard library
import os
import time
import yaml
from datetime import datetime
from typing import Dict
from enum import Enum
from contextlib import contextmanager
import re
import pytz
import uuid

from app.utils.provide_json_itineraries import ProvideJsonItineraries, Message, Role, MessageType, DataToCreateItinerary
import logging
logger = logging.getLogger(__name__)

# Third-party libraries
from openai import OpenAI
from dotenv import load_dotenv
from num2words import num2words

@contextmanager
def timer(operation_name: str):
    start_time = time.time()
    try:
        yield
    finally:
        end_time = time.time()
        execution_time = end_time - start_time
        print(f"{operation_name}: {execution_time:.2f} seconds")


class Budget(Enum):
    BUDGET_FRIENDLY = "Budget-friendly"
    MODERATE = "Moderate"
    LUXURY = "Luxury"


class TravelStyle(Enum):
    FAMILY_FRIENDLY = "Family-friendly"
    ADVENTURE = "Adventure"
    CULTURAL = "Cultural"

load_dotenv()

class ItineraryGenerator:  
    def __init__(self, model: str = "gpt-4-turbo-preview", max_tokens: int = 2000, temperature: float = 0.3):
        self.api_key = os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OpenAI API key is required. Set OPENAI_API_KEY environment variable or pass it to constructor.")
        
        self.prompts_folder_path = os.getenv('PROMPTS_FOLDER_PATH')
        self.client = OpenAI(api_key=self.api_key)
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.config_folder_path = os.getenv('CONFIG_FOLDER_PATH')
        self.days_config = self._load_config("days_mapping.yaml")
        self.preferences_config = self._load_config("preferences_mapping.yaml")
        self.destinations_config = self._load_config("destinations_mapping.yaml")
        self._validate_configs()
        
    def _validate_configs(self):
        if 'ukrainian_destinations' not in self.destinations_config:
            raise RuntimeError("destinations_mapping.json must contain 'ukrainian_destinations' section")
        
        if 'default_preferences' not in self.preferences_config:
            raise RuntimeError("preferences_mapping.json must contain 'default_preferences' section")
        
        if 'default_duration' not in self.days_config:
            raise RuntimeError("days_mapping.json must contain 'default_duration' section")
    
    def _load_config(self, config_file: str) -> dict:
        try:
            if not self.config_folder_path:
                raise ValueError("CONFIG_FOLDER_PATH environment variable is not set. Please add it to your .env file.")
            
            config_path = os.path.join(self.config_folder_path, config_file)
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except FileNotFoundError as e:
            raise RuntimeError(f"Configuration file not found: {config_file}")
        except yaml.YAMLError as e:
            raise RuntimeError(f"Invalid YAML in configuration file: {config_file}")
        except Exception as e:
            raise RuntimeError(f"Failed to load configuration {config_file}: {e}")
    
    def _load_prompt_template(self, template_name: str) -> str:
        try:
            template_path = os.path.join(self.prompts_folder_path, f"{template_name}.txt")
            with open(template_path, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except FileNotFoundError as e:
            raise RuntimeError(f"Prompt template file not found: {template_name}.txt")
        except PermissionError as e:
            raise RuntimeError(f"Permission denied accessing prompt template: {template_name}.txt")
        except UnicodeDecodeError as e:
            raise RuntimeError(f"Failed to decode prompt template {template_name}.txt: {e}")
        except OSError as e:
            raise RuntimeError(f"OS error loading prompt template {template_name}: {e}")

    def _create_system_prompt(self) -> str:
        return self._load_prompt_template("system_prompt")


    def _create_user_prompt(self, destination: str, duration: str, interests: str, 
                           budget: str, travel_style: str, additional_context: str = "") -> str:
        template = self._load_prompt_template("user_prompt")
        
        additional_context_text = f"Additional Context: {additional_context}" if additional_context else ""
        
        return template.format(
            duration=duration,
            destination=destination,
            interests=interests,
            budget=budget,
            travel_style=travel_style,
            additional_context=additional_context_text
        )

    def generate_itinerary(self, prompt_text: str) -> str:
        """
        Generate an itinerary using the OpenAI API with timing measurement.
        
        Args:
            prompt_text: The user prompt for itinerary generation
            
        Returns:
            str: Generated itinerary text
            
        Raises:
            RuntimeError: For API errors or missing usage information
            ValueError: For authentication errors
        """
        response = None
        with timer("itinerary generation"):
            try:
                system_prompt = self._create_system_prompt()

                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt_text}
                    ],
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    top_p=0.9,
                    frequency_penalty=0.1,
                    presence_penalty=0.1
                )
                
                if not hasattr(response, 'choices') or not response.choices:
                    raise RuntimeError("No choices returned from OpenAI API")
                
                first_choice = response.choices[0]
                if not hasattr(first_choice, 'message') or not first_choice.message:
                    raise RuntimeError("No message in API response choice")
                
                if not hasattr(first_choice.message, 'content') or not first_choice.message.content:
                    raise RuntimeError("No content in API response message")
                
                itinerary = first_choice.message.content.strip()
                return itinerary
                
            except Exception as e:
                error_message = str(e)
                
                if "authentication" in error_message.lower() or "api_key" in error_message.lower():
                    raise ValueError("Authentication failed. Please check your OpenAI API key.")
                elif "rate limit" in error_message.lower():
                    raise RuntimeError("Rate limit exceeded. Please try again later.")
                else:
                    raise RuntimeError(f"OpenAI API error: {error_message}")

    def get_days(self, user_input_lower: str) -> str:
        day_pattern = self.days_config["patterns"]["day_pattern"]
        week_pattern = self.days_config["patterns"]["week_pattern"]
        written_numbers = self.days_config["written_numbers"]
        written_weeks = self.days_config["written_weeks"]
        default_duration = self.days_config["default_duration"]
        
        day_match = re.search(day_pattern, user_input_lower)
        if day_match:
            days = int(day_match.group(1))
            return f"{days} days"
        
        for i in range(1, 101):  # Check numbers 1-100
            written_number = num2words(i).lower()
            if f"{written_number} days" in user_input_lower or f"{written_number} day" in user_input_lower:
                return f"{i} days"
        
        for word, number in written_numbers.items():
            if f"{word} days" in user_input_lower or f"{word} day" in user_input_lower:
                return f"{number} days"
        
        week_match = re.search(week_pattern, user_input_lower)
        if week_match:
            weeks = int(week_match.group(1))
            days = weeks * 7
            return f"{days} days"
        
        for i in range(1, 31):  # Check weeks 1-30
            written_week = num2words(i).lower()
            if f"{written_week} week" in user_input_lower or f"{written_week} weeks" in user_input_lower:
                days = i * 7
                return f"{days} days"
            
        for week_phrase, days in written_weeks.items():
            if week_phrase in user_input_lower:
                return f"{days} days"
        
        return default_duration

    def extract_destination_from_text(self, user_input_lower: str) -> str:
        """
        Extract destination information from user input.
        
        Args:
            user_input_lower: Lowercase user input string
            
        Returns:
            str: Extracted destination or default destination
        """
        ukrainian_destinations = self.destinations_config['ukrainian_destinations']
        found_destinations = []
        
        for dest_key, dest_name in ukrainian_destinations.items():
            if dest_key in user_input_lower:
                if dest_name not in found_destinations:
                    found_destinations.append(dest_name)
        
        if len(found_destinations) > 1:
            if 'Ukraine' in found_destinations and len(found_destinations) > 1:
                found_destinations.remove('Ukraine')
            
            if len(found_destinations) == 2:
                return f"{found_destinations[0]} and {found_destinations[1]}"
            else:
                return f"{', '.join(found_destinations[:-1])}, and {found_destinations[-1]}"
        
        elif len(found_destinations) == 1:
            return found_destinations[0]
        
        else:
            return self.preferences_config["default_preferences"]["destination"]

    def parse_travel_request(self, user_input: str) -> Dict[str, str]:
        default_prefs = self.preferences_config["default_preferences"]
        
        preferences = {
            'destination': default_prefs['destination'],
            'duration': default_prefs['duration'],
            'interests': default_prefs['interests'],
            'budget': default_prefs['budget'],
            'travel_style': default_prefs['travel_style'],
            'additional_context': ''
        }
        
        user_input_lower = user_input.lower()
        
        preferences['duration'] = self.get_days(user_input_lower)
        
        preferences['destination'] = self.extract_destination_from_text(user_input_lower)
        
        # User can specify a list of interests, so we need to parse them
        interests_found = []
        interests_patterns = self.preferences_config["interests_patterns"]
        for keyword, interest in interests_patterns.items():
            if keyword in user_input_lower:
                interests_found.append(interest)
        
        if interests_found:
            preferences['interests'] = ', '.join(interests_found)
        else:
            preferences['interests'] = default_prefs['interests']
        
        # If budget is specified as "budget-friendly" and "luxury", we set it to "moderate"
        # Otherwise, we set it to the first value in the list
        budget_patterns = self.preferences_config["budget_patterns"]
        budget_found = False
        for keyword, budget_value in budget_patterns.items():
            if keyword in user_input_lower:
                try:
                    budget_list = [b for b in Budget if b.value == budget_value]
                    if any(b.value == 'Luxury' for b in budget_list) and any(b.value == 'Budget-friendly' for b in budget_list):
                        preferences['budget'] = 'Moderate'
                    if budget_list:
                        preferences['budget'] = budget_list[0]
                    else:
                        preferences['budget'] = budget_value
                except StopIteration:
                    preferences['budget'] = budget_value
                budget_found = True
                break
        
        if not budget_found:
            preferences['budget'] = default_prefs['budget']
        
        # There are can be only one travel style for one trip, so we choose the first one that matches the user input
        style_patterns = self.preferences_config["travel_style_patterns"]
        style_found = False
        for keyword, style_value in style_patterns.items():
            if keyword in user_input_lower:
                try:
                    style_enum = next(s for s in TravelStyle if s.value == style_value)
                    preferences['travel_style'] = style_enum.value
                except StopIteration:
                    preferences['travel_style'] = style_value
                style_found = True
                break
        
        if not style_found:
            preferences['travel_style'] = default_prefs['travel_style']
        
        preferences['additional_context'] = user_input
        
        return preferences

    def generate_enhanced_itinerary(self, user_input: str) -> str:
        """
        Generate an enhanced itinerary by parsing user input and creating a detailed prompt.
        
        Args:
            user_input: Raw user input string
            
        Returns:
            str: Generated itinerary text
        """
        with timer("enhanced itinerary generation"):
            preferences = self.parse_travel_request(user_input)
            
            detailed_prompt = self._create_user_prompt(
                destination=preferences['destination'],
                duration=preferences['duration'],
                interests=preferences['interests'],
                budget=preferences['budget'],
                travel_style=preferences['travel_style'],
                additional_context=preferences['additional_context']
            )
            
            return self.generate_itinerary(detailed_prompt)

class CLISessionHistory:
    def __init__(self):
        self.session_history = []
        self.session_id = self.generate_session_id()
        self.started_at = self.generate_iso_timestamp()
        # In my demo I will use Kiev timezone
        self.timezone_offset = self.generate_timezone_with_pytz('Europe/Kiev')

    def save_to_session_history(self, user_input: str, itinerary: str, preferences: Dict[str, str]):
        session_entry = {
            'timestamp': self.generate_iso_timestamp(),
            'user_input': user_input,
            'preferences': preferences,
            'itinerary': itinerary
        }
        self.session_history += [session_entry]

    def generate_iso_timestamp(self):
        """Generate ISO timestamp in format: YYYY-MM-DDTHH:MM:SS+HH:MM"""
        # Get current time
        now = datetime.now()
        
        # Remove microseconds
        now = now.replace(microsecond=0)
        
        # Add timezone
        tz = pytz.timezone('Europe/Kiev')  # UTC+3
        now_with_tz = tz.localize(now)
        
        # Convert to ISO format
        return now_with_tz.isoformat()

    def generate_session_id(self):
        """Generate a unique session_id"""
        return str(uuid.uuid4())

    def generate_timezone_with_pytz(self, timezone: str):
        """Generate the current timezone with pytz"""
        # Get the current local time
        local_tz = pytz.timezone(timezone)  # UTC+3
        now = datetime.now()
        
        # Localize the time
        local_time = local_tz.localize(now)
        
        # Get the offset
        offset = local_time.strftime('%z')
        
        # Format as +03:00
        return f"{offset[:3]}:{offset[3:]}"

    def save_conversation_to_file(self):
        try:
            history_dir = os.getenv('HISTORY_FOLDER_DIRECTORY')
            if not history_dir:
                raise ValueError("HISTORY_FOLDER_DIRECTORY environment variable is not set. Please add it to your .env file.")
            
            if not os.path.exists(history_dir):
                os.makedirs(history_dir)
            
            timestamp = self.generate_iso_timestamp()
            filename = f"conversation_{timestamp}.json"
            filepath = os.path.join(history_dir, filename)
            provide_json_itineraries = ProvideJsonItineraries()
            messages = []
            for session in self.session_history:
                messages.append(Message(text=session['user_input'], sender=Role.USER, message_type=MessageType.TEXT))
                messages.append(Message(text=session['itinerary'], sender=Role.ASSISTANT, message_type=MessageType.TEXT))
            
            # Until we have no authorization and a large number of users instead of user_id I will use a 
            user_data = DataToCreateItinerary(
                user_id="user_message_id",
                session_id=self.session_id,
                started_at=self.started_at,
                timezone_offset=self.timezone_offset
            )
            session_history_json = provide_json_itineraries.provide_json_itinerary(messages, user_data)
            provide_json_itineraries.save_itinerary_from_dict(session_history_json, filepath)
            return filepath
        except (PermissionError, OSError, UnicodeEncodeError, Exception) as e:
            logger.error(f"Failed to save conversation to file: {e}")
            return None

