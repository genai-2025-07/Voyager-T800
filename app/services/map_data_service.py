import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any
from dataclasses import dataclass
from dotenv import load_dotenv

import googlemaps

load_dotenv()

@dataclass
class OpeningHours:
    type: str
    week_start: str
    week_end: str
    last_refreshed: str
    weekly: Dict[str, List[Dict[str, str]]]

@dataclass
class Coordinates:
    lat: float
    lng: float

@dataclass
class Address:
    postal_code: str
    administrative_area_level_1: str
    administrative_area_level_2: str
    sublocality_level_1: str
    formatted_address: str


class GoogleMapService:
    def __init__(self):
        api_key = os.getenv('GOOGLE_MAPS_API_KEY')
        if not api_key:
            print("❌ Error: Set GOOGLE_MAPS_API_KEY environment variable")
        self.client = googlemaps.Client(key=api_key)
        self.target_address_types = [
            "postal_code",
            "administrative_area_level_1", 
            "administrative_area_level_2",
            "sublocality_level_1"
        ]

    def get_entire_address(self, place_id: str) -> Address:
        try:
            place = self.client.place(place_id=place_id)
            return self._extract_address_components(place)
        except Exception as e:
            print(f"❌ Error: {e}")
            return None

    def get_address_components_as_list(self, place_id: str) -> List[Dict[str, Any]]:
        try:
            place = self.client.place(place_id=place_id)
            return place.get("result", {}).get("address_components", [])
        except Exception as e:
            print(f"❌ Error: {e}")
            return None

    def get_formatted_address(self, place_id: str) -> str:
        try:
            place = self.client.place(place_id=place_id)
            return place.get("result", {}).get("formatted_address", "")
        except Exception as e:
            print(f"❌ Error: {e}")
            return None

    def get_phone_number(self, place_id: str) -> str:
        try:
            place = self.client.place(place_id=place_id)
            return place.get("result", {}).get("international_phone_number", "")
        except Exception as e:
            print(f"❌ Error: {e}")
            return None

    def get_opening_hours(self, current_opening_hours: Dict[str, Any]) -> OpeningHours:
        today = datetime.now()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        
        week_start_str = week_start.strftime("%Y-%m-%d")
        week_end_str = week_end.strftime("%Y-%m-%d")
        last_refreshed = week_end.replace(hour=21, minute=0, second=0).isoformat() + "+03:00"
        
        weekly = {}
        weekday_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        
        periods = current_opening_hours.get("periods", [])
        
        for period in periods:
            open_info = period.get("open", {})
            close_info = period.get("close", {})
            
            day_name = weekday_names[open_info.get("day", 0)]
            start_time = open_info.get("time", "12:00")
            end_time = close_info.get("time", "21:00")
            
            start_formatted = f"{start_time[:2]}:{start_time[2:]}"
            end_formatted = f"{end_time[:2]}:{end_time[2:]}"
            
            if day_name not in weekly:
                weekly[day_name] = []
            
            weekly[day_name].append({
                "start": start_formatted,
                "end": end_formatted
            })
        
        for day in weekday_names:
            if day not in weekly:
                if day in ["Saturday", "Sunday"]:
                    weekly[day] = [{"start": "10:00", "end": "21:00"}]
                else:
                    weekly[day] = [{"start": "12:00", "end": "21:00"}]
        
        return OpeningHours(
            type="weekly",
            week_start=week_start_str,
            week_end=week_end_str,
            last_refreshed=last_refreshed,
            weekly=weekly
        )

    def get_place_id(self, place: str) -> str:
        try:
            return self.client.find_place(place, "textquery")
        except Exception as e:
            print(f"❌ Error: {e}")
            return None

    def get_places_ids(self, places: List[str]) -> List[str]:
        try:
            place_ids = []
            for place in places:
                place_ids.append(self.client.find_place(place, "textquery"))
            return place_ids
        except Exception as e:
            print(f"❌ Error: {e}")
            return None

    def get_coordinates(self, geometry: Dict[str, Any]) -> Coordinates:
        location = geometry.get("location", {})
        return Coordinates(
            lat=location.get("lat", 0.0),
            lng=location.get("lng", 0.0)
        )
    
    def get_price_level(self, place_id: str) -> int:
        try:
            place = self.client.place(place_id=place_id)
            return place.get("result", {}).get("price_level", 0)
        except Exception as e:
            print(f"❌ Error: {e}")
            return None

    def get_rating(self, place_id: str) -> float:
        try:
            place = self.client.place(place_id=place_id)
            return place.get("result", {}).get("rating", 0.0)
        except Exception as e:
            print(f"❌ Error: {e}")
            return None

    def get_tags(self, place_id: str) -> List[str]:
        try:
            place = self.client.place(place_id=place_id)
            return place.get("result", {}).get("types", [])
        except Exception as e:
            print(f"❌ Error: {e}")
            return None
    
    def get_wheelchair_accessible_entrance(self, place_id: str) -> bool:
        try:
            place = self.client.place(place_id=place_id)
            return place.get("result", {}).get("wheelchair_accessible_entrance", False)
        except Exception as e:
            print(f"❌ Error: {e}")
            return None

    def get_serves_reviews(self, place_id: str) -> bool:
        try:
            place = self.client.place(place_id=place_id)
            return place.get("result", {}).get("serves_reviews", False)
        except Exception as e:
            print(f"❌ Error: {e}")
            return None

    def get_url(self, place_id: str) -> str:
        try:
            place = self.client.place(place_id=place_id)
            return place.get("result", {}).get("url", "")
        except Exception as e:
            print(f"❌ Error: {e}")
            return None

    def process_place_data(self, place_data: Dict[str, Any]) -> Dict[str, Any]:
        result = place_data.get("result", {})
        
        address_components = result.get("address_components", [])
        address_extracted = {}
        for component in address_components:
            component_types = component.get("types", [])
            long_name = component.get("long_name", "")
            
            for target_type in self.target_address_types:
                if target_type in component_types:
                    address_extracted[target_type] = long_name
                    break
        
        processed_data = {
            "postal_code": address_extracted.get("postal_code", ""),
            "administrative_area_level_1": address_extracted.get("administrative_area_level_1", ""),
            "administrative_area_level_2": address_extracted.get("administrative_area_level_2", ""),
            "sublocality_level_1": address_extracted.get("sublocality_level_1", ""),
            
            "address": result.get("formatted_address", ""),
            "phone_number": result.get("international_phone_number", ""),
            "place_id": result.get("place_id", ""),
            "url": result.get("url", ""),
            
            "coordinates": self.get_coordinates(result.get("geometry", {})),
            
            "rating": result.get("rating", 0.0),
            "reviews": result.get("reviews", []),
            
            "price_level": result.get("price_level", 0),
            "tags": result.get("types", []),
            "wheelchair_accessible_entrance": result.get("wheelchair_accessible_entrance", False),
            
            "serves_beer": result.get("serves_beer", False),
            "serves_breakfast": result.get("serves_breakfast", False),
            "serves_brunch": result.get("serves_brunch", False),
            "serves_dinner": result.get("serves_dinner", False),
            "serves_lunch": result.get("serves_lunch", False),
            "serves_vegetarian_food": result.get("serves_vegetarian_food", False),
            "serves_wine": result.get("serves_wine", False),
            "takeout": result.get("takeout", False),
        }
        
        current_opening_hours = result.get("current_opening_hours")
        if current_opening_hours:
            processed_data["opening_hours"] = self.get_opening_hours(current_opening_hours)
        
        return processed_data
    
    def process_from_json(self, json_file_path: str) -> Dict[str, Any]:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            place_data = json.load(f)
        
        return self.process_place_data(place_data)
    
    def save_processed_data(self, processed_data: Dict[str, Any], output_path: str) -> None:
        serializable_data = {}
        
        for key, value in processed_data.items():
            if isinstance(value, (OpeningHours, Coordinates)):
                serializable_data[key] = value.__dict__
            else:
                serializable_data[key] = value
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(serializable_data, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Processed data saved to {output_path}")

    def _extract_address_components(self, place: Dict[str, Any]) -> Address:
        address_components = place.get("result", {}).get("address_components", [])
        extracted = {}
        
        for component in address_components:
            component_types = component.get("types", [])
            long_name = component.get("long_name", "")
            
            for target_type in self.target_address_types:
                if target_type in component_types:
                    extracted[target_type] = long_name
                    break
        
        return Address(
            postal_code=extracted.get("postal_code", ""),
            administrative_area_level_1=extracted.get("administrative_area_level_1", ""),
            administrative_area_level_2=extracted.get("administrative_area_level_2", ""),
            sublocality_level_1=extracted.get("sublocality_level_1", ""),
            formatted_address=place.get("result", {}).get("formatted_address", "")
        )


if __name__ == "__main__":
    service = GoogleMapService()
    try:
        processed_data = service.process_from_json("place_data.json")
        service.save_processed_data(processed_data, "processed_place_data.json")
    except FileNotFoundError:
        print("⚠️  place_data.json not found. Run collect_attractions_metadata.py first.")
