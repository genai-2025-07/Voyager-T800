from pydantic import BaseModel, Field, validator
from typing import List, Optional

class ItineraryDay(BaseModel):
    day: int = Field(description='Day number of the trip (1, 2, 3, etc.)')
    location: str = Field(description='Main location/city for this day')
    activities: List[str] = Field(description='List of activities planned for this day', min_items=1, max_items=10)
    accommodation: Optional[str] = Field(description='Where to stay (hotel, hostel, etc.)', default=None)
    budget_estimate: Optional[str] = Field(description='Estimated budget for the day', default=None)
    
    @validator('day')
    def day_must_be_positive(cls, v):
        if v < 1:
            raise ValueError('Day must be positive number')
        return v
    
    @validator('location')
    def location_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Location cannot be empty')
        return v.strip()
    
    @validator('activities')
    def activities_not_empty(cls, v):
        if not v:
            raise ValueError('Activities list cannot be empty')
        return [activity.strip() for activity in v if activity.strip()]

class TravelItinerary(BaseModel):
    destination: str = Field(description='Main destination of the trip')
    duration_days: int = Field(description='Total number of days for the trip')
    transportation: str = Field(description='Main transportation method', 
                               pattern=r'^(driving|walking|cycling|public_transit|flight|mixed)$')
    itinerary: List[ItineraryDay] = Field(description='Day-by-day itinerary', min_items=1)
    
    @validator('duration_days')
    def duration_positive(cls, v):
        if v < 1:
            raise ValueError('Duration must be at least 1 day')
        return v
    
    @validator('itinerary')
    def check_itinerary_consistency(cls, v, values):
        if 'duration_days' in values and len(v) != values['duration_days']:
            raise ValueError(f'Itinerary length ({len(v)}) must match duration_days ({values["duration_days"]})')
        
        days = [item.day for item in v]
        expected_days = list(range(1, len(v) + 1))
        if sorted(days) != expected_days:
            raise ValueError(f'Days must be sequential: expected {expected_days}, got {sorted(days)}')
        
        return v