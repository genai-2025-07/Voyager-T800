import os 
import sys
from dotenv import load_dotenv
project_root = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'app'))
from utils.parser_functions import parse_itinerary_output, export_to_json, export_to_dict
from utils.manual_parser import ManualItineraryParser
load_dotenv()
def test_with_ai():
   """Test with AI LLM parser"""
   test_request = """
  Trip to Amsterdam for 3 days.
Day 1: Arrival in Amsterdam
- Visit to the Van Gogh Museum
- Canal Walk 
- Dinner at a Restaurant near Dam Square

Day 2: City Tour
- City Bike Tour
- Visit to Albert Cuyp Market
- Concert at Paradiso

Day 3: Last Day
- Return to Amsterdam
- Dinner at a Restaurant near the Canal
   """

   api_key = os.getenv('OPENAI_API_KEY')
   
   result = parse_itinerary_output(test_request, api_key)
   
   print("Generated itinerary (AI):")
   for day in result:
       print(f"Day {day.day}: {day.location}")
       for activity in day.activities:
           print(f"  • {activity}")
   
   print("\nJSON export:")
   print(export_to_json(result))
   
   print("\nDict export:")
   dict_result = export_to_dict(result)
   for day_dict in dict_result:
       print(day_dict)

def test_manual_parser():
   from utils.manual_parser import ManualItineraryParser
   
   test_text =  test_text = """
Trip to Amsterdam for 3 days.
Day 1: Arrival in Amsterdam
- Visit to the Van Gogh Museum
- Canal Walk 
- Dinner at a Restaurant near Dam Square

Day 2: City Tour
- City Bike Tour
- Visit to Albert Cuyp Market
- Concert at Paradiso

Day 3: Last Day
- Return to Amsterdam
- Dinner at a Restaurant near the Canal
    """
    
   parser = ManualItineraryParser(debug=False)
   result = parser.parse_itinerary_text(test_text)
   
   print("Generated itinerary (Manual Parser):")
   print(f"Destination: {result.destination}")
   print(f"Duration: {result.duration_days} days")
   print(f"Transportation: {result.transportation}")
   print()
   
   for day in result.itinerary:
       print(f"Day {day.day}: {day.location}")
       for activity in day.activities:
           print(f"  • {activity}")
   
   print("\nJSON export (Manual):")
   print(export_to_json(result.itinerary))



if __name__ == "__main__":
   test_with_ai()
   test_manual_parser()

   
