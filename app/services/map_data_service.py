import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import asdict
from dotenv import load_dotenv

import googlemaps
import pandas as pd
import yaml
from tqdm import tqdm
import pytz

from app.services.map_data_models import (
    OpeningHours, Coordinates, Address, MapDataServiceConfig,
    ApiConfig, TimezoneConfig, OpeningHoursConfig, OpeningHoursDefaults,
    TimeConfig, CoordinatesSection, CoordinatesConfig, AddressConfig
)

load_dotenv()

class GoogleMapService:
    def __init__(self):
        """
        Initialize the Google Maps service with configuration from environment.
        
        Loads configuration from the file specified in MAP_DATA_CONFIG_PATH
        environment variable and initializes the Google Maps API client.
        
        Raises:
            FileNotFoundError: If configuration file is not found
            ValueError: If configuration is invalid or missing required fields
            PermissionError: If Google Maps API key is not set
        """
        self.configs = self._load_yaml_config(os.getenv('MAP_DATA_CONFIG_PATH'))
        self.client = googlemaps.Client(key=self.configs.api.google_maps_api_key)
        self._place_cache = {}

    def _load_yaml_config(self, config_path: str) -> MapDataServiceConfig:
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_dict = yaml.safe_load(f)
            
            if not config_dict:
                raise ValueError("Configuration file is empty")
            
            api_key = config_dict.get("api", {}).get("google_maps_api_key")
            if api_key.startswith("${") and api_key.endswith("}"):
                env_var = api_key[2:-1]
                api_key = os.getenv(env_var)
                if not api_key:
                    raise ValueError(f"Environment variable {env_var} is not set")

            api_config = ApiConfig(google_maps_api_key=api_key)
            
            timezone_config = TimezoneConfig(
                default=config_dict["timezone"]["default"]
            )
            
            opening_hours_config = OpeningHoursConfig(
                defaults=OpeningHoursDefaults(
                    weekdays=TimeConfig(**config_dict["opening_hours"]["defaults"]["weekdays"]),
                    weekends=TimeConfig(**config_dict["opening_hours"]["defaults"]["weekends"])
                )
            )
            
            coordinates_section = CoordinatesSection(
                default=CoordinatesConfig(**config_dict["coordinates"]["default"])
            )
            
            address_config = AddressConfig(
                target_address_types=config_dict["address"]["target_address_types"]
            )
            
            config = MapDataServiceConfig(
                api=api_config,
                timezone=timezone_config,
                opening_hours=opening_hours_config,
                coordinates=coordinates_section,
                address=address_config,
                attraction_csv_path=config_dict["attraction_csv_path"],
                output_csv_path=config_dict["output_csv_path"],
                output_json_path=config_dict["output_json_path"]
            )
            
            return config
            
        except FileNotFoundError:
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in configuration file: {e}")
        except KeyError as e:
            raise ValueError(f"Missing required configuration key: {e}")
        except Exception as e:
            raise ValueError(f"Error loading configuration: {e}")

    def get_entire_address(self, place_id: str) -> Optional[Address]:
        """
        Retrieve complete address information for a place.
        
        Args:
            place_id: Google Maps place ID to retrieve address for
            
        Returns:
            Address object containing formatted address and address components,
            or None if place details cannot be retrieved
            
        Raises:
            ValueError: If place_id is invalid or empty
        """
        try:
            place_details = self._get_place_details(place_id)
            if place_details:
                return self._extract_address_components({"result": place_details})
            return None
        except Exception as e:
            print(f"❌ Error: {e}")
            return None

    def get_address_components_as_list(self, place_id: str) -> Optional[List[Dict[str, Any]]]:
        """
        Retrieve raw address components as a list of dictionaries.
        
        Args:
            place_id: Google Maps place ID to retrieve address components for
            
        Returns:
            List of address component dictionaries from Google Maps API,
            or None if place details cannot be retrieved
            
        Raises:
            ValueError: If place_id is invalid or empty
        """
        try:
            place_details = self._get_place_details(place_id)
            return place_details.get("address_components", []) if place_details else None
        except Exception as e:
            print(f"❌ Error: {e}")
            return None

    def get_formatted_address(self, place_id: str) -> Optional[str]:
        """
        Retrieve the formatted address string for a place.
        
        Args:
            place_id: Google Maps place ID to retrieve formatted address for
            
        Returns:
            Formatted address string, or None if place details cannot be retrieved
            
        Raises:
            ValueError: If place_id is invalid or empty
        """
        try:
            place_details = self._get_place_details(place_id)
            return place_details.get("formatted_address", "") if place_details else None
        except Exception as e:
            print(f"❌ Error: {e}")
            return None

    def get_phone_number(self, place_id: str) -> Optional[str]:
        """
        Retrieve the international phone number for a place.
        
        Args:
            place_id: Google Maps place ID to retrieve phone number for
            
        Returns:
            International phone number string, or None if place details cannot be retrieved
            
        Raises:
            ValueError: If place_id is invalid or empty
        """
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
            timezone_obj = pytz.timezone(self.configs.timezone.default)
            last_refreshed_dt = timezone_obj.localize(week_end.replace(hour=21, minute=0, second=0))
            last_refreshed = last_refreshed_dt.isoformat()
        except Exception as e:
            print(f"❌ Error: {e}")
            last_refreshed = week_end.replace(hour=21, minute=0, second=0).isoformat() + "Z"
        
        weekly = {}
        weekday_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        
        periods = current_opening_hours.get("periods", [])
        
        for period in periods:
            open_info = period.get("open", {})
            close_info = period.get("close", {})
            
            day_name = weekday_names[open_info.get("day", 0)]
            
            default_start = self.configs.opening_hours.defaults.weekdays.start
            default_end = self.configs.opening_hours.defaults.weekdays.end
            
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
                        "start": self.configs.opening_hours.defaults.weekends.start,
                        "end": self.configs.opening_hours.defaults.weekends.end
                    }]
                else:
                    weekly[day] = [{
                        "start": self.configs.opening_hours.defaults.weekdays.start,
                        "end": self.configs.opening_hours.defaults.weekdays.end
                    }]
        
        return OpeningHours(
            type="weekly",
            week_start=week_start_str,
            week_end=week_end_str,
            last_refreshed=last_refreshed,
            weekly=weekly
        )
    
    def _format_time_string(self, time_str: str) -> str:
        """
        Parse and format time strings from Google Maps API into HH:MM format.
        
        Accepted input formats:
        - "0900" -> "09:00"
        - "900" -> "09:00" 
        - "9" -> "09:00"
        - "1430" -> "14:30"
        - "14:30" -> "14:30" (already formatted)
        - "2:30" -> "02:30"
        
        Args:
            time_str: Time string from Google Maps API (e.g., "0900", "1430")
            
        Returns:
            Formatted time string in HH:MM format
        """
        if not time_str or not isinstance(time_str, str):
            raise ValueError("Time string must be a non-empty string")
        
        cleaned_str = ''.join(c for c in time_str if c.isdigit() or c == ':')
        
        if not cleaned_str:
            raise ValueError("Time string contains no valid time data")
        
        if ':' in cleaned_str:
            try:
                time_obj = datetime.strptime(cleaned_str, "%H:%M")
                return time_obj.strftime("%H:%M")
            except ValueError:
                raise ValueError(f"Invalid time format: {time_str}")
        
        digits_only = ''.join(filter(str.isdigit, cleaned_str))
        
        if not digits_only:
            raise ValueError("Time string contains no digits")
        
        try:
            if len(digits_only) == 4:
                hours = digits_only[:2]
                minutes = digits_only[2:]
            elif len(digits_only) == 3:
                hours = digits_only[0]
                minutes = digits_only[1:]
            elif len(digits_only) == 2:
                hours = digits_only
                minutes = '00'
            elif len(digits_only) == 1:
                hours = digits_only
                minutes = '00'
            else:
                raise ValueError(f"Unsupported time format: {time_str}")
            
            if not (0 <= int(hours) <= 23):
                raise ValueError(f"Hours must be between 0-23, got: {hours}")
            if not (0 <= int(minutes) <= 59):
                raise ValueError(f"Minutes must be between 0-59, got: {minutes}")
            
            return f"{hours}:{minutes}"
            
        except ValueError as e:
            if "Hours must be" in str(e) or "Minutes must be" in str(e):
                raise e
            raise ValueError(f"Invalid time format: {time_str}")
        except Exception as e:
            raise ValueError(f"Error parsing time string '{time_str}': {e}")

    def get_place_id(self, place: str) -> Optional[str]:
        """
        Find the Google Maps place ID for a given place name.
        
        Args:
            place: Place name or description to search for
            
        Returns:
            Google Maps place ID string, or None if place cannot be found
            
        Raises:
            ValueError: If place parameter is invalid or empty
        """
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
        """
        Find Google Maps place IDs for a list of place names.
        
        Args:
            places: List of place names or descriptions to search for
            
        Returns:
            List of Google Maps place IDs, or None if no places can be found
            
        Raises:
            ValueError: If places parameter is invalid or empty
        """
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
        """
        Extract coordinates from Google Maps geometry data.
        
        Args:
            geometry: Geometry dictionary from Google Maps API response
            
        Returns:
            Coordinates object containing latitude and longitude
            
        Raises:
            ValueError: If geometry data is invalid or missing coordinates
        """
        location = geometry.get("location", {})
        if not location.get("lat") or not location.get("lng"):
            raise ValueError("Coordinates are not valid")
        return Coordinates(
            lat=location.get("lat"),
            lng=location.get("lng")
        )
    
    def get_price_level(self, place_id: str) -> Optional[int]:
        """
        Retrieve the price level for a place.
        
        Args:
            place_id: Google Maps place ID to retrieve price level for
            
        Returns:
            Price level integer (0-4), or None if place details cannot be retrieved
            
        Raises:
            ValueError: If place_id is invalid or empty
        """
        try:
            place_details = self._get_place_details(place_id)
            return place_details.get("price_level", 0) if place_details else None
        except Exception as e:
            print(f"❌ Error: {e}")
            return None

    def get_rating(self, place_id: str) -> Optional[float]:
        """
        Retrieve the rating for a place.
        
        Args:
            place_id: Google Maps place ID to retrieve rating for
            
        Returns:
            Rating float (0.0-5.0), or None if place details cannot be retrieved
            
        Raises:
            ValueError: If place_id is invalid or empty
        """
        try:
            place_details = self._get_place_details(place_id)
            return place_details.get("rating", 0.0) if place_details else None
        except Exception as e:
            print(f"❌ Error: {e}")
            return None

    def get_tags(self, place_id: str) -> Optional[List[str]]:
        """
        Retrieve the place types/tags for a place.
        
        Args:
            place_id: Google Maps place ID to retrieve tags for
            
        Returns:
            List of place type strings, or None if place details cannot be retrieved
            
        Raises:
            ValueError: If place_id is invalid or empty
        """
        try:
            place_details = self._get_place_details(place_id)
            return place_details.get("types", []) if place_details else None
        except Exception as e:
            print(f"❌ Error: {e}")
            return None
    
    def get_wheelchair_accessible_entrance(self, place_id: str) -> Optional[bool]:
        """
        Check if a place has wheelchair accessible entrance.
        
        Args:
            place_id: Google Maps place ID to check accessibility for
            
        Returns:
            Boolean indicating wheelchair accessibility, or None if place details cannot be retrieved
            
        Raises:
            ValueError: If place_id is invalid or empty
        """
        try:
            place_details = self._get_place_details(place_id)
            return place_details.get("wheelchair_accessible_entrance", False) if place_details else None
        except Exception as e:
            print(f"❌ Error: {e}")
            return None

    def get_url(self, place_id: str) -> Optional[str]:
        """
        Retrieve the Google Maps URL for a place.
        
        Args:
            place_id: Google Maps place ID to retrieve URL for
            
        Returns:
            Google Maps URL string, or None if place details cannot be retrieved
            
        Raises:
            ValueError: If place_id is invalid or empty
        """
        try:
            place_details = self._get_place_details(place_id)
            return place_details.get("url", "") if place_details else None
        except Exception as e:
            print(f"❌ Error: {e}")
            return None

    def get_coordinates_object(self, place_id: str) -> Optional[Coordinates]:
        """
        Retrieve coordinates object for a place with fallback to default coordinates.
        
        Args:
            place_id: Google Maps place ID to retrieve coordinates for
            
        Returns:
            Coordinates object, or default coordinates if place details cannot be retrieved
            
        Raises:
            ValueError: If place_id is invalid or empty
        """
        place_details = self._get_place_details(place_id)
        geometry = place_details.get("geometry", {})
        if isinstance(geometry, dict):
            try:
                coordinates_obj = self.get_coordinates(geometry)
                coordinates = asdict(coordinates_obj)
            except (ValueError, AttributeError):
                def_lat = self.configs.coordinates.default.lat
                def_lng = self.configs.coordinates.default.lng
                coordinates = {"lat": def_lat, "lng": def_lng}

        return coordinates
    
    def get_opening_hours_object(self, place_id: str) -> Optional[OpeningHours]:
        """
        Retrieve opening hours object for a place with fallback to default hours.
        
        Args:
            place_id: Google Maps place ID to retrieve opening hours for
            
        Returns:
            OpeningHours object, or default opening hours if place details cannot be retrieved
            
        Raises:
            ValueError: If place_id is invalid or empty, or if place details cannot be retrieved
        """
        place_details = self._get_place_details(place_id)
        if not place_details:
            raise ValueError(f"Could not retrieve place details for place_id: {place_id}")
        
        try:
            current_opening_hours = place_details.get("opening_hours")
            if current_opening_hours and isinstance(current_opening_hours, dict):
                opening_hours_obj = self.get_opening_hours(current_opening_hours)
                opening_hours = asdict(opening_hours_obj)
                return opening_hours
            return self.get_default_opening_hours()
        except Exception as e:
            print(f"❌ Error: {e}")
            return self.get_default_opening_hours()

    def get_default_opening_hours(self) -> OpeningHours:
        """
        Generate default opening hours based on configuration.
        
        Creates a weekly schedule using the default opening hours from configuration,
        with weekdays and weekends having different schedules.
        
        Returns:
            OpeningHours object with default weekly schedule
            
        Raises:
            ValueError: If configuration is invalid or missing required fields
        """
        today = datetime.now()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        
        week_start_str = week_start.strftime("%Y-%m-%d")
        week_end_str = week_end.strftime("%Y-%m-%d")

        last_refreshed = datetime.now().isoformat()

        return OpeningHours(
            type="weekly",
            week_start=week_start_str,
            week_end=week_end_str,
            last_refreshed=last_refreshed,
            weekly={
                "Monday": [{
                    "start": self.configs.opening_hours.defaults.weekdays.start,
                    "end": self.configs.opening_hours.defaults.weekdays.end
                }],
                "Tuesday": [{
                    "start": self.configs.opening_hours.defaults.weekdays.start,
                    "end": self.configs.opening_hours.defaults.weekdays.end
                }],
                "Wednesday": [{
                    "start": self.configs.opening_hours.defaults.weekdays.start,
                    "end": self.configs.opening_hours.defaults.weekdays.end
                }],
                "Thursday": [{
                    "start": self.configs.opening_hours.defaults.weekdays.start,
                    "end": self.configs.opening_hours.defaults.weekdays.end
                }],
                "Friday": [{
                    "start": self.configs.opening_hours.defaults.weekdays.start,
                    "end": self.configs.opening_hours.defaults.weekdays.end
                }],
                "Saturday": [{
                    "start": self.configs.opening_hours.defaults.weekends.start,
                    "end": self.configs.opening_hours.defaults.weekends.end
                }],
                "Sunday": [{
                    "start": self.configs.opening_hours.defaults.weekends.start,
                    "end": self.configs.opening_hours.defaults.weekends.end
                }]
            }
        )

    def _create_place_data_object(self, place_id: str, address_obj: Address, coordinates: Coordinates, opening_hours: OpeningHours) -> Dict[str, Any]:
        place_details = self._get_place_details(place_id)
        if not place_details:
            raise ValueError(f"Could not retrieve place details for place_id: {place_id}")
        
        processed_data =  {
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
            "reviews": self._normalize_reviews(place_details.get("reviews")),
            
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
            "opening_hours": opening_hours,
        }

        return processed_data
    
    def _normalize_reviews(self, reviews_data: Any) -> List[Dict[str, Any]]:
        if not reviews_data:
            return []
        
        if isinstance(reviews_data, list):
            normalized_reviews = []
            for review in reviews_data:
                if isinstance(review, dict):
                    normalized_reviews.append(review)
                else:
                    print(f"Skipping non-dictionary review: {type(review)}")
            return normalized_reviews
        
        if isinstance(reviews_data, dict):
            return [reviews_data]
            
        return []
    
    def process_place_data(self, place_id: str) -> Dict[str, Any]:
        """
        Process complete place data for a given place ID.
        
        Retrieves and processes all available data for a place including address,
        coordinates, opening hours, ratings, and other metadata.
        
        Args:
            place_id: Google Maps place ID to process
            
        Returns:
            Dictionary containing all processed place data
            
        Raises:
            ValueError: If place_id is invalid or required data cannot be retrieved
        """
        if not place_id or not isinstance(place_id, str):
            raise ValueError("place_id must be a non-empty string")
        
        address_obj = self.get_entire_address(place_id)
        if not address_obj:
            raise ValueError(f"Could not retrieve address for place_id: {place_id}")
        
        coordinates = self.get_coordinates_object(place_id)
        if not coordinates:
            raise ValueError(f"Could not retrieve coordinates for place_id: {place_id}")
        
        opening_hours = self.get_opening_hours_object(place_id)
        
        return self._create_place_data_object(place_id, address_obj, coordinates, opening_hours)
    
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
        """
        Save processed place data to a JSON file.
        
        Converts dataclass objects to dictionaries and saves the data in JSON format
        with proper encoding and formatting.
        
        Args:
            processed_data: Dictionary containing processed place data
            output_path: File path where to save the JSON data
            
        Raises:
            ValueError: If processed_data is invalid or output_path is invalid
            IOError: If file cannot be written to the specified path
        """
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
            
            for target_type in self.configs.address.target_address_types:
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
        """
        Clear the internal place details cache.
        
        Removes all cached place details to free memory and ensure fresh data
        on subsequent API calls.
        """
        self._place_cache.clear()

    def process_all_places_json(self, attraction_csv_path: str) -> None:
        """
        Process all places from CSV and save individual JSON files for each place.
        
        Reads attractions from CSV file, retrieves place IDs, processes each place,
        and saves the data as individual JSON files in the configured output directory.
        
        Args:
            attraction_csv_path: Path to the CSV file containing attractions
            
        Raises:
            ValueError: If CSV file is invalid or required columns are missing
            FileNotFoundError: If CSV file does not exist
        """
        df = pd.read_csv(attraction_csv_path)
        cities = df["City"]
        attractions = df["Attraction"]
        place_ids = []
        for city, attraction in zip(cities, attractions):
            place_id = self.get_place_id(f"{attraction}, {city}")
            if place_id:
                place_ids.append(place_id)
        for place_id in place_ids:
            processed_data = self.process_place_data(place_id)
            self.save_processed_data(processed_data, f"{self.configs.output_json_path}/{place_id}.json")

    def _validate_csv_columns(self, df: pd.DataFrame, required_columns: List[str]) -> tuple[pd.Series, pd.Series]:
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"CSV is missing required columns: {missing_columns}. "
                           f"Available columns: {list(df.columns)}")
        
        empty_columns = []
        for col in required_columns:
            if df[col].isna().all() or (df[col] == "").all():
                empty_columns.append(col)
        
        if empty_columns:
            raise ValueError(f"CSV has empty required columns: {empty_columns}")
        
        if not df["City"].dtype == 'object' or not df["Attraction"].dtype == 'object':
            raise ValueError("City and Attraction columns must contain text data")
        
        if len(df) == 0:
            raise ValueError("CSV file is empty")
        
        cities = df["City"].fillna("").astype(str)
        attractions = df["Attraction"].fillna("").astype(str)
        
        valid_mask = (cities != "") & (attractions != "")
        cities = cities[valid_mask]
        attractions = attractions[valid_mask]
        
        if len(cities) == 0:
            raise ValueError("No valid data found after filtering empty values")
        
        return cities, attractions

    def process_all_places_csv(self, attraction_csv_path: str) -> None:
        """
        Process all places from CSV and save metadata to a single CSV file.
        
        Reads attractions from CSV file, validates the data, processes each place
        with progress indication, and saves all metadata to a single CSV file.
        
        Args:
            attraction_csv_path: Path to the CSV file containing attractions
            
        Raises:
            ValueError: If CSV file is invalid, required columns are missing, or processing fails
            FileNotFoundError: If CSV file does not exist
        """
        try:
            df = pd.read_csv(attraction_csv_path)
            cities, attractions = self._validate_csv_columns(df, ["City", "Attraction"])
            
            all_processed_data = []
            
            with tqdm(
                total=len(cities),
                desc="Processing attractions",
                unit="attraction",
                bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]"
            ) as pbar:
                for city, attraction in zip(cities, attractions):
                    try:
                        pbar.set_description(f"Processing: {attraction[:30]}...")
                        
                        place_id = self.get_place_id(f"{attraction}, {city}")
                        if not place_id:
                            pbar.write(f"Could not find place_id for: {attraction}, {city}")
                            pbar.update(1)
                            continue
                        
                        processed_data = self.process_place_data(place_id)
                        
                        processed_data["name"] = attraction
                        processed_data["city"] = city
                        
                        all_processed_data.append(processed_data)
                        
                        pbar.update(1)
                        
                    except Exception as e:
                        pbar.write(f"❌ Error processing {attraction}, {city}: {e}")
                        pbar.update(1)
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
            
            output_path = self.configs.output_csv_path
            result_df.to_csv(output_path, index=False, encoding='utf-8')
            
        except Exception as e:
            raise ValueError(f"Error processing CSV: {e}")