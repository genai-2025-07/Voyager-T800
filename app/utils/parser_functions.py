import json
from typing import List
from app.models.llms.itinerary import ItineraryDay
from app.utils.llm_parser import ItineraryParserAgent
from app.utils.manual_parser import ManualItineraryParser


def parse_itinerary_output(response: str) -> List[ItineraryDay]:
    """
    Parses itinerary output using AI parser with manual parser fallback.
    
    Args:
        response (str): Raw itinerary response text to parse.
        
    Returns:
        List[ItineraryDay]: List of parsed itinerary days.
        
    Raises:
        TypeError: If response is not a string.
        ValueError: If response is empty or contains invalid data.
        Exception: If both AI and manual parsing fail completely.
    """
    if not isinstance(response, str):
        raise TypeError("Response must be a string")
    
    if not response.strip():
        raise ValueError("Response cannot be empty")
    
    try:
        parser = ItineraryParserAgent()
        itinerary = parser.parse_itinerary_output(response)
        
        if not hasattr(itinerary, 'itinerary') or not itinerary.itinerary:
            raise ValueError("AI parser returned empty or invalid itinerary")
            
        return itinerary.itinerary
        
    except (AttributeError, KeyError, ValueError) as ai_error:
        print(f"AI parsing error: {ai_error}. Trying manual parser...")
        
        try:
            manual_parser = ManualItineraryParser(debug=False)
            manual_result = manual_parser.parse_itinerary_text(response)
            
            if not hasattr(manual_result, 'itinerary') or not manual_result.itinerary:
                raise ValueError("Manual parser returned empty or invalid itinerary")
                
            return manual_result.itinerary
            
        except (AttributeError, KeyError, ValueError, IndexError) as manual_error:
            print(f"Manual parsing also failed: {manual_error}")
            return [ItineraryDay(day=1, location="Unknown", activities=["Plan your trip"])]
            
    except Exception as unexpected_error:
        print(f"Unexpected error during parsing: {unexpected_error}")
        return [ItineraryDay(day=1, location="Unknown", activities=["Plan your trip"])]


def validate_itinerary(itinerary_days: List[ItineraryDay]) -> bool:
    """
    Validates that itinerary days are properly sequenced and structured.
    
    Args:
        itinerary_days (List[ItineraryDay]): List of itinerary days to validate.
        
    Returns:
        bool: True if itinerary is valid, False otherwise.
        
    Raises:
        TypeError: If itinerary_days is not a list or contains invalid day objects.
        AttributeError: If ItineraryDay objects are missing required attributes.
    """
    try:
        if not isinstance(itinerary_days, list):
            raise TypeError("itinerary_days must be a list")
        
        if not itinerary_days:
            return False
        
        # Validate each day object has required attributes
        for day in itinerary_days:
            if not hasattr(day, 'day'):
                raise AttributeError(f"ItineraryDay object missing 'day' attribute")
            if not isinstance(day.day, int):
                raise TypeError(f"Day number must be an integer, got {type(day.day)}")
        
        days = [day.day for day in itinerary_days]
        expected = list(range(1, len(itinerary_days) + 1))
        
        return sorted(days) == expected
        
    except (TypeError, AttributeError) as validation_error:
        print(f"Validation error: {validation_error}")
        return False
    except Exception as unexpected_error:
        print(f"Unexpected error during validation: {unexpected_error}")
        return False


def export_to_json(itinerary_days: List[ItineraryDay]) -> str:
    """
    Exports itinerary days to JSON string format.
    
    Args:
        itinerary_days (List[ItineraryDay]): List of itinerary days to export.
        
    Returns:
        str: JSON string representation of the itinerary.
        
    Raises:
        json.JSONEncodeError: If the data cannot be serialized to JSON.
    """
    try:
        data = [day.dict() for day in itinerary_days]
        return json.dumps(data, ensure_ascii=False, indent=2)
    except json.JSONEncodeError as e:
        raise json.JSONEncodeError(f"Failed to serialize itinerary to JSON: {e}")


def export_to_dict(itinerary_days: List[ItineraryDay]) -> List[dict]:
    """
    Exports itinerary days to list of dictionaries format.
    
    Args:
        itinerary_days (List[ItineraryDay]): List of itinerary days to export.
        
    Returns:
        List[dict]: List of dictionaries representing the itinerary days.
        
    Raises:
        AttributeError: If ItineraryDay objects don't have dict() method.
    """
    try:
        return [day.dict() for day in itinerary_days]
    except AttributeError as e:
        raise AttributeError(f"Error converting itinerary to dict: {e}")