#!/usr/bin/env python3
# Standard library
import os
import time
import json
import datetime
from typing import Dict, Optional
from enum import Enum

# Third-party libraries
from openai import OpenAI
from dotenv import load_dotenv

# Local imports
from app.config.logging_config import get_logger


class Budget(Enum):
    BUDGET_FRIENDLY = "Budget-friendly"
    MODERATE = "Moderate"
    LUXURY = "Luxury"


class TravelStyle(Enum):
    FAMILY_FRIENDLY = "Family-friendly"
    ADVENTURE = "Adventure"
    CULTURAL = "Cultural"

load_dotenv()

logger = get_logger("voyager_t800.integration")

class ItineraryGenerator:  
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4-turbo-preview", max_tokens: int = 2000, temperature: float = 0.3):
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OpenAI API key is required. Set OPENAI_API_KEY environment variable or pass it to constructor.")
        
        self.client = OpenAI(api_key=self.api_key)
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.config_folder_path = os.getenv('CONFIG_FOLDER_PATH')
        self.days_config = self._load_config("days_mapping.json")
        self.preferences_config = self._load_config("preferences_mapping.json")
        self.destinations_config = self._load_config("destinations_mapping.json")
        
        logger.info(f"ItineraryGenerator initialized successfully with model={model}, temperature={temperature}")
    
    def _load_config(self, config_file: str) -> dict:
        try:
            config_path = os.path.join(self.config_folder_path, config_file)
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError as e:
            logger.error(f"Configuration file not found: {config_file}")
            raise RuntimeError(f"Configuration file not found: {config_file}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in configuration file: {config_file}")
            raise RuntimeError(f"Invalid JSON in configuration file: {config_file}")
        except Exception as e:
            logger.error(f"Failed to load configuration {config_file}: {e}")
            raise RuntimeError(f"Failed to load configuration {config_file}: {e}")
    
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
        
        start_time = time.time()
        
        try:
            logger.info("Starting itinerary generation")
            
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
            
            itinerary = response.choices[0].message.content.strip()
            
            end_time = time.time()
            response_time = end_time - start_time
            if response.usage is not None:
                tokens_used = response.usage.total_tokens
                logger.info(f"Itinerary generated successfully in {response_time:.2f}s using {tokens_used} tokens")
            else:
                raise RuntimeError("Response usage information not available")
            
            return itinerary
            
        except Exception as e:
            if response.usage is None:
                error_msg = e.message
                logger.error(error_msg)
                raise RuntimeError(error_msg)
            elif "authentication" in e.message or "api_key" in e.message:
                error_msg = "Authentication failed. Please check your OpenAI API key."
                logger.error(error_msg) 
                raise ValueError(error_msg)
            elif "rate limit" in e.message:
                error_msg = "Rate limit exceeded. Please try again later."
                logger.error(error_msg)
                raise RuntimeError(error_msg)
            else:
                error_msg = f"OpenAI API error: {e.message}"
                logger.error(error_msg)
                raise RuntimeError(error_msg)

    def get_days(self, user_input_lower: str) -> str:
        import re
        from num2words import num2words
        
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
        
        logger.info(f"No duration pattern found, using default: {default_duration}")
        return default_duration

    def get_destinations(self, user_input_lower: str) -> str:
        try:
            ukrainian_destinations = self.destinations_config['ukrainian_destinations']
        except FileNotFoundError as e:
            logger.error(f"Destinations file not found: destinations.json")
            return self.preferences_config["default_preferences"]["destination"]
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in destinations file: {e}")
            return self.preferences_config["default_preferences"]["destination"]
        except Exception as e:
            logger.error(f"Failed to load destinations from JSON: {e}")
            return self.preferences_config["default_preferences"]["destination"]
        
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

            default_dest = self.preferences_config["default_preferences"]["destination"]
            logger.info(f"No destination pattern found, using default: {default_dest}")
            return default_dest

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
        
        preferences['destination'] = self.get_destinations(user_input_lower)
        
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
                    if 'Luxury' in budget_list and 'Budget-friendly' in budget_list:
                        preferences['budget'] = 'Moderate'
                    else:
                        preferences['budget'] = budget_list[0]
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
        
        preferences = self.parse_travel_request(user_input)
        
        detailed_prompt = self._create_user_prompt(
            destination=preferences['destination'],
            duration=preferences['duration'],
            interests=preferences['interests'],
            budget=preferences['budget'],
            travel_style=preferences['travel_style'],
            additional_context=preferences['additional_context']
        )
        
        logger.info(f"Generating itinerary for {preferences['destination']} ({preferences['duration']})")
        
        return self.generate_itinerary(detailed_prompt)


def save_to_session_history(session_history: list, user_input: str, itinerary: str, preferences: Dict[str, str]):
    session_entry = {
        'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'user_input': user_input,
        'preferences': preferences,
        'itinerary': itinerary
    }
    session_history.append(session_entry)
    return session_history

def save_conversation_to_file(session_history: list):
    try:
        history_dir = os.getenv('HISTORY_FOLDER_DIRECTION')
        if not history_dir:
            raise ValueError("HISTORY_FOLDER_DIRECTION environment variable is not set. Please add it to your .env file.")
        
        if not os.path.exists(history_dir):
            os.makedirs(history_dir)
        
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"conversation_{timestamp}.txt"
        filepath = os.path.join(history_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("Voyager T800 - Complete Conversation Session\n")
            f.write("=" * 60 + "\n\n")
            f.write(f"Session Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 60 + "\n\n")
            
            for i, entry in enumerate(session_history, 1):
                f.write(f"ITINERARY #{i}\n")
                f.write("-" * 40 + "\n")
                f.write(f"Time: {entry['timestamp']}\n")
                f.write(f"User Request: {entry['user_input']}\n\n")
                f.write("Travel Preferences:\n")
                for key, value in entry['preferences'].items():
                    f.write(f"- {key}: {value}\n")
                f.write("\n" + "-" * 40 + "\n")
                f.write(entry['itinerary'])
                f.write("\n\n" + "=" * 60 + "\n\n")
        
        print(f"💾 Complete conversation saved to: {filepath}")
        return filepath
        
    except PermissionError as e:
        logger.error(f"Permission denied creating conversation file: {e}")
        return None
    except OSError as e:
        logger.error(f"OS error saving conversation file: {e}")
        return None
    except UnicodeEncodeError as e:
        logger.error(f"Failed to encode conversation content: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error saving conversation: {e}")
        return None

