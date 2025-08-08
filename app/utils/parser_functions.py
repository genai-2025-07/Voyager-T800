import json
from typing import List
from models.llms.itinerary import ItineraryDay
from utils.llm_parser import ItineraryParserAgent
from utils.manual_parser import ManualItineraryParser
def parse_itinerary_output(response: str, api_key: str = None) -> List[ItineraryDay]:
    parser = ItineraryParserAgent(api_key=api_key)
    
    try:
        itinerary = parser.parse_itinerary_output(response)
        return itinerary.itinerary
    except Exception as e:
        print(f"AI parsing error: {e}. Trying manual parser...")
        
        try:
            manual_parser = ManualItineraryParser(debug=False)
            manual_result = manual_parser.parse_itinerary_text(response)
            return manual_result.itinerary
        except Exception as manual_error:
            print(f"Manual parsing also failed: {manual_error}")
            return [ItineraryDay(day=1, location="Unknown", activities=["Plan your trip"])]

def validate_itinerary(itinerary_days: List[ItineraryDay]) -> bool:
    if not itinerary_days:
        return False
    
    days = [day.day for day in itinerary_days]
    expected = list(range(1, len(itinerary_days) + 1))
    
    return sorted(days) == expected

def export_to_json(itinerary_days: List[ItineraryDay]) -> str:
    data = [day.dict() for day in itinerary_days]
    return json.dumps(data, ensure_ascii=False, indent=2)

def export_to_dict(itinerary_days: List[ItineraryDay]) -> List[dict]:
    return [day.dict() for day in itinerary_days]