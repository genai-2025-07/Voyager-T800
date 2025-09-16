from pydantic import BaseModel, Field, field_validator
from datetime import datetime, date
from typing import List, Optional


class Event(BaseModel):
    """Event model with validation."""

    title: str = Field(..., min_length=1, description="Event title")
    category: str = Field(..., min_length=1, description="Event category")
    date: datetime = Field(..., description="Event date and time")
    venue: str = Field(..., min_length=1, description="Event venue")
    url: str = Field(..., min_length=1, description="Event URL")

    @field_validator("title", "category", "venue")
    @classmethod
    def validate_non_empty_strings(cls, v):
        """Ensure string fields are not empty after stripping."""
        if not v or not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip()

    @field_validator("url")
    @classmethod
    def validate_url(cls, v):
        """Basic URL validation."""
        if not v or not v.strip():
            raise ValueError("URL cannot be empty")
        v = v.strip()
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("URL must start with http:// or https://")
        return v


class EventQuery(BaseModel):
    """Simple model for parsing event search queries from user input."""

    city: str = Field(..., description="Destination city")
    start_date: Optional[date] = Field(
        None,
        description="Trip start date in ISO format (YYYY-MM-DD) if mentioned, else null",
    )
    end_date: Optional[date] = Field(
        None,
        description="Trip end date in ISO format (YYYY-MM-DD) if mentioned, else null",
    )
    categories: List[str] = Field(
        default=["events"],
        description="User preferences like concerts, festivals, food, nightlife, culture, etc.",
    )

    @field_validator("end_date", "start_date", mode="before")
    @classmethod
    def none_or_date(cls, v):
        """Handle null values from LLM parsing."""
        if v in ("null", "", None):
            return None
        return v

    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def parse_date(cls, v):
        if isinstance(v, str) and v:
            return date.fromisoformat(v)
        return v

    @field_validator("city")
    @classmethod
    def validate_city(cls, v):
        """Ensure city is not empty."""
        if not v or not v.strip():
            raise ValueError("City name cannot be empty")
        return v.strip()

    @field_validator("categories")
    @classmethod
    def validate_categories(cls, v):
        """Clean up categories list."""
        if not v:
            return ["events"]
        # Remove empty strings and trim whitespace
        cleaned = [cat.strip() for cat in v if cat and cat.strip()]
        return cleaned if cleaned else ["events"]


class EventRequest(BaseModel):
    """Request model for event fetching with validation."""

    city: str = Field(..., min_length=1, description="Destination city")
    start_date: datetime = Field(..., description="Start date for event search")
    end_date: datetime = Field(..., description="End date for event search")
    categories: Optional[List[str]] = Field(
        default=None, description="Event categories to search for"
    )

    @field_validator("city")
    @classmethod
    def validate_city(cls, v):
        """Validate city name."""
        if not v or not v.strip():
            raise ValueError("City name cannot be empty")
        return v.strip()

    @field_validator("end_date")
    @classmethod
    def validate_date_range(cls, v, info):
        """Ensure end_date is after start_date."""
        if "start_date" in info.data and v <= info.data["start_date"]:
            raise ValueError("end_date must be after start_date")
        return v

    @field_validator("categories")
    @classmethod
    def validate_categories(cls, v):
        """Validate categories list."""
        if v is not None:
            if not isinstance(v, list):
                raise ValueError("categories must be a list")
            for category in v:
                if not isinstance(category, str) or not category.strip():
                    raise ValueError("All categories must be non-empty strings")
            return [cat.strip() for cat in v]
        return v
