import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import asdict
from dotenv import load_dotenv
import asyncio
from urllib.parse import urlencode

import googlemaps
import pandas as pd
import yaml
import pytz
import aiohttp
from tqdm import tqdm

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
                output_json_path=config_dict["output_json_path"],
                place_details_base_url=config_dict["place_details_base_url"],
                find_place_base_url=config_dict["find_place_base_url"]  
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

    def _build_find_place_url(self, input_text: str) -> str:
        base_url = self.configs.find_place_base_url
        params = {
            "input": input_text,
            "inputtype": "textquery",
            "key": self.configs.api.google_maps_api_key
        }
        return f"{base_url}?{urlencode(params)}"

    def _build_place_details_url(self, place_id: str) -> str:
        base_url = self.configs.place_details_base_url
        params = {
            "place_id": place_id,
            "key": self.configs.api.google_maps_api_key
        }
        return f"{base_url}?{urlencode(params)}"

    async def _fetch_place_details(self, session, place_id, sem):
        params = {"place_id": place_id}
        async with sem:
            async with session.get(self._build_place_details_url(place_id), params=params) as resp:
                data = await resp.json()
                print(f"Got {place_id}, status: {data.get('status')}")
                return data

    async def _fetch_place_id(self, session, input_text, sem):
        params = {"input": input_text, "inputtype": "textquery"}
        async with sem:
            async with session.get(self._build_find_place_url(input_text), params=params) as resp:
                data = await resp.json()
                print(f"Got {input_text}, status: {data.get('status')}")
                return (data, input_text)
    
    def _extract_address_components_dict(self, result: Dict[str, Any]) -> Dict[str, str]:
        place_data = result.get("result", {})
        address_components = place_data.get("address_components", [])
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
        place_data = place.get("result", {})
        extracted = self._extract_address_components_dict(place)
        
        return Address(
            postal_code=extracted.get("postal_code", ""),
            administrative_area_level_1=extracted.get("administrative_area_level_1", ""),
            administrative_area_level_2=extracted.get("administrative_area_level_2", ""),
            sublocality_level_1=extracted.get("sublocality_level_1", ""),
            formatted_address=place_data.get("formatted_address", "")
        )

    def _get_entire_address(self, place_data: Dict[str, Any]) -> Optional[Address]:
        try:
            if place_data:
                return self._extract_address_components(place_data)
            return None
        except Exception as e:
            print(f"❌ Error: {e}")
            return None

    def _get_coordinates(self, geometry: Dict[str, Any]) -> Coordinates:
        location = geometry.get("location", {})
        if not location.get("lat") or not location.get("lng"):
            raise ValueError("Coordinates are not valid")
        return Coordinates(
            lat=location.get("lat"),
            lng=location.get("lng")
        )

    def _get_coordinates_object(self, place_data: Dict[str, Any]) -> Optional[Coordinates]:
        geometry = place_data.get("geometry", {})
        if isinstance(geometry, dict):
            try:
                coordinates_obj = self._get_coordinates(geometry)
                coordinates = asdict(coordinates_obj)
            except (ValueError, AttributeError):
                def_lat = self.configs.coordinates.default.lat
                def_lng = self.configs.coordinates.default.lng
                coordinates = {"lat": def_lat, "lng": def_lng}

        return coordinates

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

    def _get_opening_hours(self, current_opening_hours: Dict[str, Any]) -> Optional[OpeningHours]:
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

    def _get_default_opening_hours(self) -> OpeningHours:
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

    def _get_opening_hours_object(self, place_data: Dict[str, Any]) -> Optional[OpeningHours]:
        if not place_data:
            raise ValueError(f"Could not retrieve place details for place_id: {place_data}")
        
        try:
            current_opening_hours = place_data.get("result", {}).get("opening_hours")
            if current_opening_hours and isinstance(current_opening_hours, dict):
                opening_hours_obj = self._get_opening_hours(current_opening_hours)
                opening_hours = asdict(opening_hours_obj)
                return opening_hours
            return self._get_default_opening_hours()
        except Exception as e:
            print(f"❌ Error: {e}")
            return self._get_default_opening_hours()
        
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

    def _create_place_data_object(self, place_data: Dict[str, Any], address_obj: Address, coordinates: Coordinates, opening_hours: OpeningHours) -> Dict[str, Any]:
        place_details = place_data.get("result", {})
        if not place_details:
            raise ValueError(f"Could not retrieve place details for place_id: {place_data}")
        
        processed_data =  {
            "postal_code": address_obj.postal_code,
            "administrative_area_level_1": address_obj.administrative_area_level_1,
            "administrative_area_level_2": address_obj.administrative_area_level_2,
            "sublocality_level_1": address_obj.sublocality_level_1,

            "address": place_details.get("formatted_address", "") or "",
            "phone_number": place_details.get("formatted_phone_number", "") or "",
            "place_id": place_details.get("place_id", "") or "",
            "url": place_details.get("url", "") or "",

            "coordinates": coordinates,

            "rating": place_details.get("rating", 0.0) or 0.0,
            "reviews": self._normalize_reviews(place_details.get("reviews")),
            
            "price_level": place_details.get("price_level", 0) or 0,
            "tags": place_details.get("types", []) or [],
            "wheelchair_accessible_entrance": place_details.get("wheelchair_accessible_entrance", False) or False,
            
            "serves_beer": place_details.get("serves_beer", False) or False,
            "serves_breakfast": place_details.get("serves_breakfast", False) or False,
            "serves_brunch": place_details.get("serves_brunch", False) or False,
            "serves_dinner": place_details.get("serves_dinner", False) or False,
            "serves_lunch": place_details.get("serves_lunch", False) or False,
            "serves_vegetarian_food": place_details.get("serves_vegetarian_food", False) or False,
            "serves_wine": place_details.get("serves_wine", False) or False,
            "takeout": place_details.get("takeout", False) or False,
            "opening_hours": opening_hours,
        }

        return processed_data
    
    def _process_place_data(self, place_data: Dict[str, Any]) -> Dict[str, Any]:
        if not place_data or not isinstance(place_data, dict):
            raise ValueError("place_data must be a non-empty dictionary")
        
        address_obj = self._get_entire_address(place_data)
        if not address_obj:
            raise ValueError(f"Could not retrieve address for place_id: {place_data}")
        
        coordinates = self._get_coordinates_object(place_data.get("result", {}))
        if not coordinates:
            raise ValueError(f"Could not retrieve coordinates for place_id: {place_data}")
        
        opening_hours = self._get_opening_hours_object(place_data)
        
        return self._create_place_data_object(place_data, address_obj, coordinates, opening_hours)


    async def process_all_places_csv_async(self, attraction_csv_path: str) -> None:
        sem = asyncio.Semaphore(20)

        df = pd.read_csv(attraction_csv_path)
        cities, attractions = self._validate_csv_columns(df, ["City", "Attraction"])

        input_texts = [f"{attraction}, {city}" for attraction, city in zip(attractions, cities)]
        places_ids = []
        async with aiohttp.ClientSession() as session:
            tasks = [self._fetch_place_id(session, input_text, sem) for input_text in input_texts]
            results = await asyncio.gather(*tasks)
            
            for result in results:
                if result and result[0].get('status') == 'OK' and result[0].get('candidates'):
                    place_id = (result[0]['candidates'][0].get('place_id'), result[1])
                    if place_id:
                        places_ids.append(place_id)
                    else:
                        print(f"⚠️  No place_id found in result: {result}")
                else:
                    print(f"⚠️  Invalid result or no candidates: {result}")
            
            print(f"✅ Found {len(places_ids)} valid place IDs out of {len(input_texts)} requests")

        if not places_ids:
            print("❌ No valid place IDs found, cannot proceed")
            return

        places_data = []
        async with aiohttp.ClientSession() as session:
            tasks = [self._fetch_place_details(session, place_id[0], sem) for place_id in places_ids]
            places_data = await asyncio.gather(*tasks)    
        
        if not places_data:
            print("❌ No valid place data found, cannot proceed")
            return
        
        all_processed_data = []
        with tqdm(
                total=len(places_data),
                desc="Processing attractions",
                unit="attraction",
                bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]"
            ) as pbar:
            for place_data in places_data:
                processed_data = self._process_place_data(place_data)
                for place_id, input_text in places_ids:
                    if place_id == processed_data.get("place_id"):
                        processed_data["name"] = input_text.split(",")[0].strip()
                        processed_data["city"] = input_text.split(",")[1].strip()
                        break
                all_processed_data.append(processed_data)
                pbar.update(1)

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