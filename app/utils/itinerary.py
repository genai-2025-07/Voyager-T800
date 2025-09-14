from pydantic import BaseModel, Field, validator
from typing import List, Optional, ClassVar
from datetime import datetime
from enum import Enum
import uuid
import logging

logger = logging.getLogger(__name__)

class TransportationType(Enum):
    """Supported transportation types"""
    DRIVING = "driving"
    WALKING = "walking"
    CYCLING = "cycling"
    PUBLIC_TRANSIT = "public_transit"
    FLIGHT = "flight"
    MIXED = "mixed"
    
    @classmethod
    def from_string(cls, value: str) -> 'TransportationType':
        """Convert string to TransportationType enum"""
        try:
            return cls(value.lower())
        except ValueError:
            logger.warning(f"Unknown transportation type: {value}, defaulting to MIXED")
            return cls.MIXED

class RequestMetadata(BaseModel):
    """Metadata about the parsing request"""
    request_id: str = Field(
        description='Unique identifier for this parsing request', 
        default_factory=lambda: str(uuid.uuid4())
    )
    timestamp: datetime = Field(
        description='When the request was processed', 
        default_factory=datetime.now
    )
    original_request: str = Field(description='Original text that was parsed')
    parser_used: str = Field(
        description='Which parser was used (ai, manual, fallback)', 
        default='unknown'
    )
    
    VALID_PARSERS: ClassVar[set] = {'ai', 'manual', 'fallback', 'unknown'}
    
    @validator('original_request')
    def request_not_empty(cls, v):
        if not isinstance(v, str):
            raise ValueError('Original request must be a string')
        if not v or not v.strip():
            raise ValueError('Original request cannot be empty')
        return v.strip()
    
    @validator('parser_used')
    def valid_parser(cls, v):
        if v not in cls.VALID_PARSERS:
            raise ValueError(f'Parser must be one of {cls.VALID_PARSERS}')
        return v

class ItineraryDay(BaseModel):
    """Represents a single day in travel itinerary"""    
    MAX_ACTIVITIES: ClassVar[int] = 15
    MIN_ACTIVITIES: ClassVar[int] = 1
    
    day: int = Field(description='Day number of the trip (1, 2, 3, etc.)')
    location: str = Field(description='Main location/city for this day')
    activities: List[str] = Field(
        description='List of activities planned for this day', 
        min_items=MIN_ACTIVITIES, 
        max_items=MAX_ACTIVITIES
    )
    accommodation: Optional[str] = None
    budget_estimate: Optional[str] = None
    
    @validator('day')
    def day_must_be_positive(cls, v):
        if not isinstance(v, int):
            raise ValueError('Day must be an integer')
        if v < 1:
            raise ValueError('Day must be positive number')
        return v
    
    @validator('location')
    def location_not_empty(cls, v):
        if not isinstance(v, str):
            raise ValueError('Location must be a string')
        if not v or not v.strip():
            raise ValueError('Location cannot be empty')
        return v.strip()
    
    @validator('activities')
    def activities_not_empty(cls, v):
        if not v:
            raise ValueError('Activities list cannot be empty')
        filtered_activities = [activity.strip() for activity in v if activity.strip()]
        if not filtered_activities:
            raise ValueError('Activities list cannot contain only empty strings')
        if len(filtered_activities) < cls.MIN_ACTIVITIES:
            raise ValueError(f'Must have at least {cls.MIN_ACTIVITIES} activities after filtering')
        return filtered_activities

class TravelItinerary(BaseModel):
    """Complete travel itinerary with metadata"""
    destination: str = Field(description='Main destination of the trip')
    duration_days: int = Field(description='Total number of days for the trip')
    transportation: TransportationType = Field(description='Main transportation method')
    itinerary: List[ItineraryDay] = Field(description='Day-by-day itinerary', min_items=1)
    metadata: RequestMetadata = Field(description='Metadata about the parsing request')
    session_summary: Optional[str] = Field(description='Summary of the parsing session', default=None)
    language: Optional[str] = Field(description='Detected or specified language of the request', default=None)
    @validator('duration_days')
    def duration_positive(cls, v):
        if not isinstance(v, int):
            raise ValueError('Duration must be an integer')
        if v < 1:
            raise ValueError('Duration must be at least 1 day')
        return v
    
    @validator('itinerary')
    def check_itinerary_consistency(cls, v, values):
        if 'duration_days' in values:
            duration = values['duration_days']
            if not isinstance(duration, int):
                raise ValueError('Duration days must be an integer')
            if len(v) != duration:
                raise ValueError(f'Itinerary length ({len(v)}) must match duration_days ({duration})')
        
        days = [item.day for item in v]
        expected_days = list(range(1, len(v) + 1))
        if sorted(days) != expected_days:
            missing_days = set(expected_days) - set(days)
            duplicate_days = [day for day in days if days.count(day) > 1]
            error_msg = f'Days must be sequential: expected {expected_days}, got {sorted(days)}'
            if missing_days:
                error_msg += f'. Missing days: {sorted(missing_days)}'
            if duplicate_days:
                error_msg += f'. Duplicate days: {sorted(set(duplicate_days))}'
            raise ValueError(error_msg)
        
        return v
    
    @validator('transportation', pre=True)
    def parse_transportation(cls, v):
        if isinstance(v, str):
            return TransportationType.from_string(v)
        return v