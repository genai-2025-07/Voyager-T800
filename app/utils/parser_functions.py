import json
from typing import List, Union
from app.models.llms.itinerary import ItineraryDay, TravelItinerary, RequestMetadata
from app.utils.llm_parser import ItineraryParserAgent
from app.utils.manual_parser import ManualItineraryParser
from dicttoxml import dicttoxml 
import xml.dom.minidom
import logging

logger = logging.getLogger(__name__)

def parse_itinerary_output(response: str) -> TravelItinerary:
    """
    Parses itinerary output using AI parser with manual parser fallback.
    
    Args:
        response (str): Raw itinerary response text to parse.
        
    Returns:
        TravelItinerary: Complete itinerary object with metadata.
        
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
            
        return itinerary
        
    except (AttributeError, KeyError, ValueError) as ai_error:
        print(f"AI parsing error: {ai_error}. Trying manual parser...")
        
        try:
            manual_parser = ManualItineraryParser(debug=False)
            manual_result = manual_parser.parse_itinerary_text(response)
            
            if not hasattr(manual_result, 'itinerary') or not manual_result.itinerary:
                raise ValueError("Manual parser returned empty or invalid itinerary")
                
            return manual_result
            
        except (AttributeError, KeyError, ValueError, IndexError) as manual_error:
            print(f"Manual parsing also failed: {manual_error}")
            
        metadata = RequestMetadata(
            original_request=response,
            parser_used='fallback'
        )
        
        return TravelItinerary(
            destination="Unknown",
            duration_days=1,
            transportation="mixed",
            itinerary=[ItineraryDay(day=1, location="Unknown", activities=["Plan your trip"])],
            metadata=metadata
        )




def validate_itinerary(itinerary: TravelItinerary) -> bool:
    """
    Validates that travel itinerary is properly structured.
    
    Args:
        itinerary (TravelItinerary): Travel itinerary to validate.
        
    Returns:
        bool: True if itinerary is valid, False otherwise.
        
    Raises:
        TypeError: If itinerary is not a TravelItinerary object.
        AttributeError: If TravelItinerary object is missing required attributes.
    """
    try:
        if not isinstance(itinerary, TravelItinerary):
            raise TypeError("itinerary must be a TravelItinerary object")
        
        if not hasattr(itinerary, 'itinerary') or not itinerary.itinerary:
            return False
        
        # Validate each day object has required attributes
        for day in itinerary.itinerary:
            if not hasattr(day, 'day'):
                raise AttributeError(f"ItineraryDay object missing 'day' attribute")
            if not isinstance(day.day, int):
                raise TypeError(f"Day number must be an integer, got {type(day.day)}")
        
        days = [day.day for day in itinerary.itinerary]
        expected = list(range(1, len(itinerary.itinerary) + 1))
        
        return sorted(days) == expected
        
    except (TypeError, AttributeError) as validation_error:
        print(f"Validation error: {validation_error}")
        return False
    except Exception as unexpected_error:
        print(f"Unexpected error during validation: {unexpected_error}")
        return False



def export_to_json(itinerary: TravelItinerary) -> str:
    """
    Exports complete travel itinerary to JSON string format.
    
    Args:
        itinerary (TravelItinerary): Travel itinerary to export.
        
    Returns:
        str: JSON string representation of the complete itinerary.
        
    Raises:
        json.JSONEncodeError: If the data cannot be serialized to JSON.
    """
    try:
        return json.dumps(itinerary.dict(), ensure_ascii=False, indent=2, default=str)
    except json.JSONEncodeError as e:
        raise json.JSONEncodeError(f"Failed to serialize itinerary to JSON: {e}")


def export_to_dict(itinerary: TravelItinerary) -> dict:
    """
    Exports complete travel itinerary to dictionary format.
    
    Args:
        itinerary (TravelItinerary): Travel itinerary to export.
        
    Returns:
        dict: Dictionary representation of the complete itinerary.
        
    Raises:
        AttributeError: If TravelItinerary object doesn't have dict() method.
    """
    try:
        return itinerary.dict()
    except AttributeError as e:
        raise AttributeError(f"Error converting itinerary to dict: {e}")

def export_to_xml(itinerary: TravelItinerary) -> str:
    """
    Exports complete travel itinerary to XML string format.
    
    Args:
        itinerary (TravelItinerary): Travel itinerary to export.
        
    Returns:
        str: Pretty formatted XML string representation of the complete itinerary.
        
    Raises:
        Exception: If the data cannot be serialized to XML.
    """
    try:
        if not hasattr(itinerary, 'dict') or not callable(getattr(itinerary, 'dict')):
            raise AttributeError("Itinerary object must have dict() method for XML serialization")
            
        json_str = json.dumps(itinerary.dict(), default=str, ensure_ascii=False)
        data = json.loads(json_str)
        
        xml_bytes = dicttoxml(data, custom_root='travel_itinerary', attr_type=False)
        
        dom = xml.dom.minidom.parseString(xml_bytes)
        return dom.toprettyxml(indent="  ", encoding=None)
        
    except Exception as e:
        logger.error(f"Failed to serialize itinerary to XML: {e}")
        raise

    
def get_parsing_metadata(itinerary: TravelItinerary) -> RequestMetadata:
    """
    Extract parsing metadata from travel itinerary.
    
    Args:
        itinerary (TravelItinerary): Travel itinerary object.
        
    Returns:
        RequestMetadata: Metadata about how the itinerary was parsed.
        
    Raises:
        AttributeError: If itinerary doesn't have metadata attribute.
    """
    try:
        return itinerary.metadata
    except AttributeError as e:
        raise AttributeError(f"Itinerary object missing metadata: {e}")


def get_original_request(itinerary: TravelItinerary) -> str:
    """
    Get the original request text from travel itinerary metadata.
    
    Args:
        itinerary (TravelItinerary): Travel itinerary object.
        
    Returns:
        str: Original request text that was parsed.
        
    Raises:
        AttributeError: If itinerary doesn't have metadata or original_request.
    """
    try:
        return itinerary.metadata.original_request
    except AttributeError as e:
        raise AttributeError(f"Cannot access original request: {e}")


def get_parsing_timestamp(itinerary: TravelItinerary) -> str:
    """
    Get the parsing timestamp from travel itinerary metadata.
    
    Args:
        itinerary (TravelItinerary): Travel itinerary object.
        
    Returns:
        str: ISO format timestamp when the request was processed.
        
    Raises:
        AttributeError: If itinerary doesn't have metadata or timestamp.
    """
    try:
        return itinerary.metadata.timestamp.isoformat()
    except AttributeError as e:
        raise AttributeError(f"Cannot access parsing timestamp: {e}")