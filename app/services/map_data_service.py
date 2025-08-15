import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from dotenv import load_dotenv

import pytz
import googlemaps
import pandas as pd

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
        self.config_path = os.getenv('MAP_DATA_CONFIG_PATH')
        if not api_key:
            raise PermissionError("Set GOOGLE_MAPS_API_KEY environment variable")
        if not self.config_path:
            raise PermissionError("Set MAP_DATA_CONFIG_PATH environment variable")
        self.client = googlemaps.Client(key=api_key)
        self.target_address_types = [
            "postal_code",
            "administrative_area_level_1", 
            "administrative_area_level_2",
            "sublocality_level_1"
        ]
        self.timezone = self._get_timezone()
        self.default_opening_hours = self._get_default_opening_hours()
        self.default_coordinates = self._get_default_coordinates()
        self._place_cache = {}

    def _get_default_coordinates(self) -> Dict[str, float]:
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            default_coordinates = config.get("coordinates", {}).get("default")
            if not default_coordinates:
                raise ValueError("Default coordinates are not set")
            return default_coordinates
        except FileNotFoundError:
            raise ValueError(f"Configuration file not found: {self.config_path}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in configuration file: {e}")
        except KeyError as e:
            raise ValueError(f"Missing required configuration key: {e}")
        except Exception as e:
            raise ValueError(f"Error loading default coordinates configuration: {e}")
    
    def _get_default_opening_hours(self) -> Dict[str, Dict[str, str]]:
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            if not config.get("opening_hours"):
                raise ValueError("Opening hours configuration is not set")
            
            opening_hours_config = config.get("opening_hours", {})
            defaults = opening_hours_config.get("defaults", {})
            
            if not defaults.get("weekdays") or not defaults.get("weekends"):
                raise ValueError("Weekdays and weekends default opening hours are not set")
            
            weekdays_default = defaults.get("weekdays")
            weekends_default = defaults.get("weekends")
            
            return {
                "weekdays": {
                    "start": weekdays_default.get("start"),
                    "end": weekdays_default.get("end")
                },
                "weekends": {
                    "start": weekends_default.get("start"),
                    "end": weekends_default.get("end")
                }
            }
        except FileNotFoundError:
            raise ValueError(f"Configuration file not found: {self.config_path}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in configuration file: {e}")
        except KeyError as e:
            raise ValueError(f"Missing required configuration key: {e}")
        except Exception as e:
            raise ValueError(f"Error loading opening hours configuration: {e}")
    
    def _get_timezone(self) -> pytz.timezone:
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            timezone_config = config.get("timezone", {})
            default_timezone = timezone_config.get("default", "UTC")
            return pytz.timezone(default_timezone)
        except FileNotFoundError:
            raise ValueError(f"Configuration file not found: {self.config_path}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in configuration file: {e}")
        except KeyError as e:
            raise ValueError(f"Missing required configuration key: {e}")
        except Exception as e:
            raise ValueError(f"Error loading timezone configuration: {e}")

    def get_entire_address(self, place_id: str) -> Optional[Address]:
        try:
            place_details = self._get_place_details(place_id)
            if place_details:
                return self._extract_address_components({"result": place_details})
            return None
        except Exception as e:
            print(f"❌ Error: {e}")
            return None

    def get_address_components_as_list(self, place_id: str) -> Optional[List[Dict[str, Any]]]:
        try:
            place_details = self._get_place_details(place_id)
            return place_details.get("address_components", []) if place_details else None
        except Exception as e:
            print(f"❌ Error: {e}")
            return None

    def get_formatted_address(self, place_id: str) -> Optional[str]:
        try:
            place_details = self._get_place_details(place_id)
            return place_details.get("formatted_address", "") if place_details else None
        except Exception as e:
            print(f"❌ Error: {e}")
            return None

    def get_phone_number(self, place_id: str) -> Optional[str]:
        try:
            place_details = self._get_place_details(place_id)
            return place_details.get("international_phone_number", "") if place_details else None
        except Exception as e:
            print(f"❌ Error: {e}")
            return None

    def get_opening_hours(self, current_opening_hours: Dict[str, Any]) -> Optional[OpeningHours]:
        today = datetime.now()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        
        week_start_str = week_start.strftime("%Y-%m-%d")
        week_end_str = week_end.strftime("%Y-%m-%d")

        try:
            last_refreshed_dt = self.timezone.localize(week_end.replace(hour=21, minute=0, second=0))
            last_refreshed = last_refreshed_dt.isoformat()
        except Exception:
            last_refreshed = week_end.replace(hour=21, minute=0, second=0).isoformat() + "Z"
        
        weekly = {}
        weekday_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        
        periods = current_opening_hours.get("periods", [])
        
        for period in periods:
            open_info = period.get("open", {})
            close_info = period.get("close", {})
            
            day_name = weekday_names[open_info.get("day", 0)]
            
            default_start = self.default_opening_hours["weekdays"]["start"]
            default_end = self.default_opening_hours["weekdays"]["end"]
            
            start_time = open_info.get("time", default_start)
            end_time = close_info.get("time", default_end)
            
            start_formatted = self._format_time_string(start_time)
            end_formatted = self._format_time_string(end_time)
            
            if day_name not in weekly:
                weekly[day_name] = []
            
            weekly[day_name].append({
                "start": start_formatted,
                "end": end_formatted
            })
        
        for day in weekday_names:
            if day not in weekly:
                if day in ["Saturday", "Sunday"]:
                    weekly[day] = [{
                        "start": self.default_opening_hours["weekends"]["start"],
                        "end": self.default_opening_hours["weekends"]["end"]
                    }]
                else:
                    weekly[day] = [{
                        "start": self.default_opening_hours["weekdays"]["start"],
                        "end": self.default_opening_hours["weekdays"]["end"]
                    }]
        
        return OpeningHours(
            type="weekly",
            week_start=week_start_str,
            week_end=week_end_str,
            last_refreshed=last_refreshed,
            weekly=weekly
        )
    
    def _format_time_string(self, time_str: str) -> str:
        if not time_str:
            raise ValueError("Time string is empty")
        
        digits_only = ''.join(filter(str.isdigit, time_str))
        
        if not digits_only:
            raise ValueError("Time string is not a valid time")
        
        if len(digits_only) == 4:
            return f"{digits_only[:2]}:{digits_only[2:]}"
        elif len(digits_only) == 3:
            return f"0{digits_only[0]}:{digits_only[1:]}"
        elif len(digits_only) == 2:
            return f"0{digits_only[0]}:{digits_only[1]}0"
        elif len(digits_only) == 1:
            return f"0{digits_only}:00"
        else:
            try:
                hours = digits_only[:2] if len(digits_only) >= 2 else "00"
                minutes = digits_only[2:4] if len(digits_only) >= 4 else "00"
                return f"{hours}:{minutes}"
            except (ValueError, IndexError):
                raise ValueError("Time string is not a valid time")

    def get_place_id(self, place: str) -> Optional[str]:
        try:
            response = self.client.find_place(place, "textquery")
            
            if response and "candidates" in response and response["candidates"]:
                place_id = response["candidates"][0].get("place_id")
                if place_id:
                    return place_id
            
            return None
        except Exception as e:
            print(f"❌ Error: {e}")
            return None

    def get_places_ids(self, places: List[str]) -> Optional[List[str]]:
        try:
            place_ids = []
            for place in places:
                place_id = self.get_place_id(place)
                if place_id:
                    place_ids.append(place_id)
            return place_ids if place_ids else None
        except Exception as e:
            print(f"❌ Error: {e}")
            return None

    def get_coordinates(self, geometry: Dict[str, Any]) -> Coordinates:
        location = geometry.get("location", {})
        if not location.get("lat") or not location.get("lng"):
            raise ValueError("Coordinates are not valid")
        return Coordinates(
            lat=location.get("lat"),
            lng=location.get("lng")
        )
    
    def get_price_level(self, place_id: str) -> Optional[int]:
        try:
            place_details = self._get_place_details(place_id)
            return place_details.get("price_level", 0) if place_details else None
        except Exception as e:
            print(f"❌ Error: {e}")
            return None

    def get_rating(self, place_id: str) -> Optional[float]:
        try:
            place_details = self._get_place_details(place_id)
            return place_details.get("rating", 0.0) if place_details else None
        except Exception as e:
            print(f"❌ Error: {e}")
            return None

    def get_tags(self, place_id: str) -> Optional[List[str]]:
        try:
            place_details = self._get_place_details(place_id)
            return place_details.get("types", []) if place_details else None
        except Exception as e:
            print(f"❌ Error: {e}")
            return None
    
    def get_wheelchair_accessible_entrance(self, place_id: str) -> Optional[bool]:
        try:
            place_details = self._get_place_details(place_id)
            return place_details.get("wheelchair_accessible_entrance", False) if place_details else None
        except Exception as e:
            print(f"❌ Error: {e}")
            return None

    def get_url(self, place_id: str) -> Optional[str]:
        try:
            place_details = self._get_place_details(place_id)
            return place_details.get("url", "") if place_details else None
        except Exception as e:
            print(f"❌ Error: {e}")
            return None

    def process_place_data(self, place_id: str) -> Dict[str, Any]:
        if not place_id or not isinstance(place_id, str):
            raise ValueError("place_id must be a non-empty string")
        
        address_obj = self.get_entire_address(place_id)
        if not address_obj:
            raise ValueError(f"Could not retrieve address for place_id: {place_id}")
        
        place_details = self._get_place_details(place_id)
        if not place_details:
            raise ValueError(f"Could not retrieve place details for place_id: {place_id}")
        
        coordinates = None
        geometry = place_details.get("geometry", {})
        if isinstance(geometry, dict):
            try:
                coordinates_obj = self.get_coordinates(geometry)
                coordinates = asdict(coordinates_obj)
            except (ValueError, AttributeError):
                def_lat = self.default_coordinates.get("lat")
                def_lng = self.default_coordinates.get("lng")
                coordinates = {"lat": def_lat, "lng": def_lng}
        
        opening_hours = None
        current_opening_hours = place_details.get("current_opening_hours")
        if current_opening_hours and isinstance(current_opening_hours, dict):
            try:
                opening_hours_obj = self.get_opening_hours(current_opening_hours)
                opening_hours = asdict(opening_hours_obj)
            except Exception:
                opening_hours = None
        
        processed_data = {
            "postal_code": address_obj.postal_code,
            "administrative_area_level_1": address_obj.administrative_area_level_1,
            "administrative_area_level_2": address_obj.administrative_area_level_2,
            "sublocality_level_1": address_obj.sublocality_level_1,
            
            "address": self.get_formatted_address(place_id) or "",
            "phone_number": self.get_phone_number(place_id) or "",
            "place_id": place_id,
            "url": self.get_url(place_id) or "",
            
            "coordinates": coordinates,
            
            "rating": self.get_rating(place_id) or 0.0,
            "reviews": place_details.get("reviews", []),
            
            "price_level": self.get_price_level(place_id) or 0,
            "tags": self.get_tags(place_id) or [],
            "wheelchair_accessible_entrance": self.get_wheelchair_accessible_entrance(place_id) or False,
            
            "serves_beer": place_details.get("serves_beer", False),
            "serves_breakfast": place_details.get("serves_breakfast", False),
            "serves_brunch": place_details.get("serves_brunch", False),
            "serves_dinner": place_details.get("serves_dinner", False),
            "serves_lunch": place_details.get("serves_lunch", False),
            "serves_vegetarian_food": place_details.get("serves_vegetarian_food", False),
            "serves_wine": place_details.get("serves_wine", False),
            "takeout": place_details.get("takeout", False),
        }
        
        if opening_hours:
            processed_data["opening_hours"] = opening_hours
        
        return processed_data
    
    def _validate_place_data_structure(self, place_data: Dict[str, Any]) -> bool:
        if not isinstance(place_data, dict):
            return False
        
        if "result" not in place_data:
            return False
        
        result = place_data["result"]
        if not isinstance(result, dict):
            return False
        
        required_fields = ["place_id"]
        for field in required_fields:
            if field not in result:
                return False
        
        return True
    
    def _safe_get_nested(self, data: Dict[str, Any], *keys: str, default: Any = None) -> Any:
        current = data
        for key in keys:
            if not isinstance(current, dict):
                return default
            current = current.get(key, default)
            if current is None:
                return default
        return current
    
    def process_from_json(self, json_file_path: str) -> Dict[str, Any]:
        try:
            with open(json_file_path, 'r', encoding='utf-8') as f:
                place_data = json.load(f)
        except FileNotFoundError:
            raise ValueError(f"JSON file not found: {json_file_path}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in file {json_file_path}: {e}")
        except Exception as e:
            raise ValueError(f"Error reading JSON file {json_file_path}: {e}")
        
        if not self._validate_place_data_structure(place_data):
            raise ValueError(f"Invalid place data structure in {json_file_path}")
        
        return self.process_place_data(place_data)
    
    def save_processed_data(self, processed_data: Dict[str, Any], output_path: str) -> None:
        serializable_data = {}
        
        for key, value in processed_data.items():
            if hasattr(value, '__dataclass_fields__'):
                serializable_data[key] = asdict(value)
            else:
                serializable_data[key] = value
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(serializable_data, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Processed data saved to {output_path}")

    def _extract_address_components_dict(self, result: Dict[str, Any]) -> Dict[str, str]:
        address_components = result.get("address_components", [])
        if not isinstance(address_components, list):
            address_components = []
        
        extracted = {}
        for component in address_components:
            if not isinstance(component, dict):
                continue
            component_types = component.get("types", [])
            long_name = component.get("long_name", "")
            
            for target_type in self.target_address_types:
                if target_type in component_types:
                    extracted[target_type] = long_name
                    break
        
        return extracted
    
    def _extract_address_components(self, place: Dict[str, Any]) -> Address:
        result = place.get("result", {})
        extracted = self._extract_address_components_dict(result)
        
        return Address(
            postal_code=extracted.get("postal_code", ""),
            administrative_area_level_1=extracted.get("administrative_area_level_1", ""),
            administrative_area_level_2=extracted.get("administrative_area_level_2", ""),
            sublocality_level_1=extracted.get("sublocality_level_1", ""),
            formatted_address=result.get("formatted_address", "")
        )
    
    def _get_place_details(self, place_id: str) -> Optional[Dict[str, Any]]:
        if place_id in self._place_cache:
            return self._place_cache[place_id]
        
        try:
            place_data = self.client.place(place_id=place_id)
            if place_data and "result" in place_data:
                self._place_cache[place_id] = place_data["result"]
                return place_data["result"]
            return None
        except Exception as e:
            print(f"❌ Error getting place details for {place_id}: {e}")
            return None
    
    def clear_cache(self) -> None:
        self._place_cache.clear()

    def process_all_places_json(self, attraction_csv_path: str) -> None:
        with open(self.config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        df = pd.read_csv(attraction_csv_path)
        citys = df["City"]
        attractions = df["Attraction"]
        place_ids = []
        for city, attraction in zip(citys, attractions):
            place_id = self.get_place_id(f"{attraction}, {city}")
            if place_id:
                place_ids.append(place_id)
        for place_id in place_ids:
            processed_data = self.process_place_data(place_id)
            self.save_processed_data(processed_data, f"{config.get('output_json_path')}/{place_id}.json")

    def process_all_places_csv(self, attraction_csv_path: str) -> None:
        try:
            df = pd.read_csv(attraction_csv_path)
            
            if "City" not in df.columns or "Attraction" not in df.columns:
                raise ValueError("CSV must contain 'City' and 'Attraction' columns")
            
            cities = df["City"]
            attractions = df["Attraction"]
            
            all_processed_data = []
            
            for city, attraction in zip(cities, attractions):
                try:
                    place_id = self.get_place_id(f"{attraction}, {city}")
                    if not place_id:
                        print(f"⚠️  Could not find place_id for: {attraction}, {city}")
                        continue
                    
                    processed_data = self.process_place_data(place_id)
                    
                    processed_data["name"] = attraction
                    processed_data["city"] = city
                    
                    all_processed_data.append(processed_data)
                    
                except Exception as e:
                    print(f"❌ Error processing {attraction}, {city}: {e}")
                    continue
            
            if not all_processed_data:
                return
            
            result_df = pd.DataFrame(all_processed_data)
            
            columns = ["name", "city", "place_id", "address", "phone_number", "url", 
                      "coordinates", "rating", "reviews", "price_level", "tags", 
                      "wheelchair_accessible_entrance", "opening_hours",
                      "postal_code", "administrative_area_level_1", 
                      "administrative_area_level_2", "sublocality_level_1",
                      "serves_beer", "serves_breakfast", "serves_brunch", 
                      "serves_dinner", "serves_lunch", "serves_vegetarian_food", 
                      "serves_wine", "takeout"]
            
            existing_columns = [col for col in columns if col in result_df.columns]
            result_df = result_df[existing_columns]
            
            output_path = config.get("output_csv_path")
            result_df.to_csv(output_path, index=False, encoding='utf-8')
            
        except Exception as e:
            raise ValueError(f"Error processing CSV: {e}")

if __name__ == "__main__":
    service = GoogleMapService()
    with open(service.config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    attraction_csv_path = config.get("attraction_csv_path")
    service.process_all_places_csv(attraction_csv_path)