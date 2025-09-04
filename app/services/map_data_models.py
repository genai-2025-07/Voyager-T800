from dataclasses import dataclass
from typing import Dict, List
import re

# Models for the Google Maps API response
@dataclass
class OpeningHours:
    type: str
    week_start: str
    week_end: str
    last_refreshed: str
    weekly: Dict[str, List[Dict[str, str]]]
    
    def __post_init__(self):
        if not self.type:
            raise ValueError("OpeningHours.type cannot be empty")
        
        if not self.week_start or not self.week_end:
            raise ValueError("OpeningHours week_start and week_end cannot be empty")
        
        if not self.last_refreshed:
            raise ValueError("OpeningHours.last_refreshed cannot be empty")
        
        if not self.weekly or not isinstance(self.weekly, dict):
            raise ValueError("OpeningHours.weekly must be a non-empty dictionary")
        
        required_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        for day in required_days:
            if day not in self.weekly:
                raise ValueError(f"OpeningHours.weekly missing required day: {day}")
            
            day_schedule = self.weekly[day]
            if not isinstance(day_schedule, list):
                raise ValueError(f"OpeningHours.weekly[{day}] must be a list")
            
            for period in day_schedule:
                if not isinstance(period, dict):
                    raise ValueError(f"OpeningHours.weekly[{day}] periods must be dictionaries")
                if "start" not in period or "end" not in period:
                    raise ValueError(f"OpeningHours.weekly[{day}] periods must have 'start' and 'end' keys")

@dataclass
class Coordinates:
    lat: float
    lng: float
    
    def __post_init__(self):
        if not isinstance(self.lat, (int, float)) or not isinstance(self.lng, (int, float)):
            raise ValueError("Coordinates.lat and Coordinates.lng must be numeric")
        
        if not (-90 <= self.lat <= 90):
            raise ValueError(f"Coordinates.lat must be between -90 and 90, got: {self.lat}")
        
        if not (-180 <= self.lng <= 180):
            raise ValueError(f"Coordinates.lng must be between -180 and 180, got: {self.lng}")

@dataclass
class Address:
    postal_code: str
    administrative_area_level_1: str
    administrative_area_level_2: str
    sublocality_level_1: str
    formatted_address: str
    
    def __post_init__(self):
        if not isinstance(self.formatted_address, str) or not self.formatted_address.strip():
            raise ValueError("Address.formatted_address cannot be empty")
        
        for field_name in ["postal_code", "administrative_area_level_1", 
                          "administrative_area_level_2", "sublocality_level_1"]:
            field_value = getattr(self, field_name)
            if not isinstance(field_value, str):
                raise ValueError(f"Address.{field_name} must be a string, got: {type(field_value)}")




# Models for the MapDataServiceConfig
@dataclass
class TimeConfig:
    start: str
    end: str
    
    def __post_init__(self):
        if not isinstance(self.start, str) or not self.start.strip():
            raise ValueError("TimeConfig.start cannot be empty")
        
        if not isinstance(self.end, str) or not self.end.strip():
            raise ValueError("TimeConfig.end cannot be empty")
        
        time_pattern = re.compile(r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$')
        if not time_pattern.match(self.start):
            raise ValueError(f"TimeConfig.start must be in HH:MM format, got: {self.start}")
        
        if not time_pattern.match(self.end):
            raise ValueError(f"TimeConfig.end must be in HH:MM format, got: {self.end}")

@dataclass
class OpeningHoursDefaults:
    weekdays: TimeConfig
    weekends: TimeConfig
    
    def __post_init__(self):
        if not isinstance(self.weekdays, TimeConfig):
            raise ValueError("OpeningHoursDefaults.weekdays must be a TimeConfig instance")

@dataclass
class OpeningHoursConfig:
    defaults: OpeningHoursDefaults
    
    def __post_init__(self):
        if not isinstance(self.defaults, OpeningHoursDefaults):
            raise ValueError("OpeningHoursConfig.defaults must be an OpeningHoursDefaults instance")

@dataclass
class CoordinatesConfig:
    lat: float
    lng: float
    
    def __post_init__(self):
        if not isinstance(self.lat, (int, float)) or not isinstance(self.lng, (int, float)):
            raise ValueError("CoordinatesConfig.lat and CoordinatesConfig.lng must be numeric")
        
        if not (-90 <= self.lat <= 90):
            raise ValueError(f"CoordinatesConfig.lat must be between -90 and 90, got: {self.lat}")
        
        if not (-180 <= self.lng <= 180):
            raise ValueError(f"CoordinatesConfig.lng must be between -180 and 180, got: {self.lng}")


@dataclass
class CoordinatesSection:
    default: CoordinatesConfig
    
    def __post_init__(self):
        if not isinstance(self.default, CoordinatesConfig):
            raise ValueError("CoordinatesSection.default must be a CoordinatesConfig instance")


@dataclass
class TimezoneConfig:
    default: str
    
    def __post_init__(self):
        if not isinstance(self.default, str) or not self.default.strip():
            raise ValueError("TimezoneConfig.default cannot be empty")
        
        if not re.match(r'^[A-Za-z_]+/[A-Za-z_]+$', self.default):
            raise ValueError(f"TimezoneConfig.default must be in format 'Region/City', got: {self.default}")


@dataclass
class ApiConfig:
    google_maps_api_key: str
    
    def __post_init__(self):
        if not isinstance(self.google_maps_api_key, str) or not self.google_maps_api_key.strip():
            raise ValueError("ApiConfig.google_maps_api_key cannot be empty")


@dataclass
class AddressConfig:
    target_address_types: List[str]
    
    def __post_init__(self):
        if not isinstance(self.target_address_types, list):
            raise ValueError("AddressConfig.target_address_types must be a list")
        
        if not self.target_address_types:
            raise ValueError("AddressConfig.target_address_types cannot be empty")
        
        for addr_type in self.target_address_types:
            if not isinstance(addr_type, str):
                raise ValueError(f"AddressConfig.target_address_types must contain strings, got: {type(addr_type)}")

@dataclass
class MapDataServiceConfig:
    api: ApiConfig
    timezone: TimezoneConfig
    opening_hours: OpeningHoursConfig
    coordinates: CoordinatesSection
    address: AddressConfig
    attraction_csv_path: str
    output_csv_path: str
    output_json_path: str
    place_details_base_url: str
    find_place_base_url: str
    
    def __post_init__(self):
        if not isinstance(self.api, ApiConfig):
            raise ValueError("MapDataServiceConfig.api must be an ApiConfig instance")
        
        if not isinstance(self.timezone, TimezoneConfig):
            raise ValueError("MapDataServiceConfig.timezone must be a TimezoneConfig instance")
        
        if not isinstance(self.opening_hours, OpeningHoursConfig):
            raise ValueError("MapDataServiceConfig.opening_hours must be an OpeningHoursConfig instance")
        
        if not isinstance(self.coordinates, CoordinatesSection):
            raise ValueError("MapDataServiceConfig.coordinates must be a CoordinatesSection instance")
        
        if not isinstance(self.address, AddressConfig):
            raise ValueError("MapDataServiceConfig.address must be an AddressConfig instance")
        
        for path_field in ["attraction_csv_path", "output_csv_path", "output_json_path"]:
            path_value = getattr(self, path_field)
            if not isinstance(path_value, str) or not path_value.strip():
                raise ValueError(f"MapDataServiceConfig.{path_field} cannot be empty")