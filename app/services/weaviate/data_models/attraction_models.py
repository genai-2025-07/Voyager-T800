from __future__ import annotations
from typing import Dict, List, Optional, Union, Any
from pydantic import BaseModel, Field, field_validator, model_validator, field_serializer
from datetime import datetime, time, timezone
import math
import re
from enum import Enum
from urllib.parse import urlparse

class ChunkBase(BaseModel):
    chunk_text: str = Field(..., description="Text of the chunk")
    name: str = Field(..., description="Name of the attraction.")
    city: str = Field(..., description="Name of the city where attraction is located.")
    administrative_area_level_1: Optional[str] = Field(None, description="State/Province")
    administrative_area_level_2: Optional[str] = Field(None, description="County/District")
    tags: List[str] = Field(default_factory=list, description="List of category tags")
    rating: Optional[float] = Field(None, description="Average rating (0.0 - 5.0)")
    place_id: str = Field(..., description="Google Places ID")


class ChunkData(ChunkBase):
    embedding: List[float] = Field(..., description="Embdedding of the chunk")

    def to_weaviate_properties(self) -> Dict[str, Any]:
        return {
            "chunk_text": self.chunk_text,
            "name": self.name,
            "city": self.city,
            "administrative_area_level_1": self.administrative_area_level_1,
            "administrative_area_level_2": self.administrative_area_level_2,
            "tags": self.tags,
            "rating": self.rating,
            "place_id": self.place_id,
        }


class AttractionWithChunks(BaseModel):
    source_file: str
    attraction: "AttractionModel" = Field(..., description="Model with metadata for attraction.")
    chunks: Optional[List[ChunkData]]


_PHONE_NORMALIZE_RE = re.compile(r"[^\d+]")  # remove anything except digits and plus
_PHONE_E164_RE = re.compile(r"^\+?\d{7,15}$")
_URL_SIMPLE_RE = re.compile(r"^(https?://|www\.)", re.IGNORECASE)
_TAG_RE = re.compile(r"^[\w\-\s]{1,50}$", re.UNICODE)  # letters, numbers, underscore, hyphen, spaces


class CoordinatesModel(BaseModel):
    """
    Pydantic model for geographic coordinates.

    Validates latitude and longitude values with proper constraints.
    Provides geographic calculation methods and validation rules.

    Attributes:
        lat: Latitude value (-90 to 90)
        lng: Longitude value (-180 to 180)
    """
    latitude: float = Field(..., description="Latitude value (-90 to 90)")
    longitude: float = Field(..., description="Longitude value (-180 to 180)")
    
    @field_validator("latitude")
    def validate_latitude(cls, v: float) -> float:
        """Ensures latitude is within valid range."""
        if not (-90.0 <= v <= 90.0):
            raise ValueError("latitude must be between -90 and 90 degrees")
        return float(v)
    
    @field_validator("longitude")
    def validate_longitude(cls, v: float) -> float:
        """Ensures longitude is within valid range."""
        if not (-180.0 <= v <= 180.0):
            raise ValueError("longitude must be between -180 and 180 degrees")
        return float(v)

    class Config:
        anystr_strip_whitespace = True
        schema_extra = {
            "example": {"latitude": 49.8407785, "longitude": 24.0305101}
        }


_time_re = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


def _parse_hmm(v: Any) -> str:
    """
    Normalize input to 'HH:MM' string.
    Always returns a string (important).
    Accepts 'H:MM', 'HH:MM', or datetime.time.
    """
    if isinstance(v, str):
        s = v.strip()
        m = _time_re.match(s)
        if not m:
            raise ValueError(f"time must be in HH:MM format, got {v!r}")
        h, mm = m.groups()
        return f"{int(h):02d}:{mm}"
    if isinstance(v, time):
        return v.strftime("%H:%M")
    raise ValueError(f"unsupported time value: {v!r}")


def _time_to_minutes(t: Any) -> int:
    # Accept either 'HH:MM' strings or datetime.time objects
    if isinstance(t, str):
        h, m = t.split(":")
        return int(h) * 60 + int(m)
    if isinstance(t, time):
        return t.hour * 60 + t.minute
    raise ValueError("unsupported time type for comparison")


class DayOfWeek(str, Enum):
    monday = "monday"
    tuesday = "tuesday"
    wednesday = "wednesday"
    thursday = "thursday"
    friday = "friday"
    saturday = "saturday"
    sunday = "sunday"

    @classmethod
    def is_valid_key(cls, key: str) -> bool:
        return key is not None and key.lower() in {d.value for d in cls}


class TimeSlotModel(BaseModel):
    start: str = Field(..., description="Start time HH:MM")
    end: str = Field(..., description="End time HH:MM")

    # return normalized string
    @field_validator("start", mode="before")
    def validate_time_format_start(cls, v):
        return _parse_hmm(v)

    @field_validator("end", mode="before")
    def validate_time_format_end(cls, v):
        return _parse_hmm(v)

    @model_validator(mode="after")
    def validate_time_range(cls, model: "TimeSlotModel"):
        if model.start is None or model.end is None:
            raise ValueError("both start and end are required")
        if _time_to_minutes(model.start) >= _time_to_minutes(model.end):
            raise ValueError("start must be before end (no overnight ranges allowed)")
        return model

    class Config:
        str_strip_whitespace = True  # pydantic v2 name


class OpeningHoursModel(BaseModel):
    type: str = Field(None)
    week_start: Optional[str] = Field(None)
    week_end: Optional[str] = Field(None)
    last_refreshed: Optional[str] = Field(None)
    weekly: Dict[str, List[TimeSlotModel]] = Field(default_factory=dict)

    @field_validator("week_start", "week_end")
    def validate_date_format(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        if isinstance(v, str):
            try:
                datetime.strptime(v, "%Y-%m-%d")
                return v
            except ValueError:
                raise ValueError("Date must be in YYYY-MM-DD format")
        return str(v)

    @field_validator("type")
    def validate_type(cls, v: str) -> str:
        if not v or not isinstance(v, str):
            raise ValueError("type must be a non-empty string")
        return v

    @field_validator("weekly", mode="before")
    def validate_weekly_schedule_structure(cls, v):
        # ensure dict-like, normalize day keys to enum values (lowercase)
        if not isinstance(v, dict):
            raise ValueError("weekly must be a dict of day -> list of time slots")
        normalized: Dict[str, List] = {}
        for k, val in v.items():
            if isinstance(k, int):
                if not (0 <= k <= 6):
                    raise ValueError("day index must be between 0 and 6")
                day = list(DayOfWeek)[k].value
            else:
                day_candidate = str(k).strip().lower()
                if day_candidate.isdigit() and 0 <= int(day_candidate) <= 6:
                    day = list(DayOfWeek)[int(day_candidate)].value
                elif DayOfWeek.is_valid_key(day_candidate):
                    day = day_candidate
                else:
                    raise ValueError(f"invalid day key: {k}. Use monday..sunday or 0..6")
            # ensure slots are lists (defensive)
            if val is None:
                normalized[day] = []
            elif isinstance(val, list):
                normalized.setdefault(day, val)
            else:
                raise ValueError(f"slots for {k!r} must be a list")
        return normalized

    @model_validator(mode="after")
    def validate_date_range_and_slots(cls, model: "OpeningHoursModel"):
        weekly = model.weekly
        for day, slots in list(weekly.items()):
            if not isinstance(slots, list):
                raise ValueError(f"slots for {day} must be a list")
            normalized_slots: List[TimeSlotModel] = []
            for s in slots:
                if isinstance(s, TimeSlotModel):
                    normalized_slots.append(s)
                elif isinstance(s, dict):
                    normalized_slots.append(TimeSlotModel(**s))
                else:
                    raise ValueError(f"invalid timeslot value for {day}: {s!r}")
            normalized_slots.sort(key=lambda ts: _time_to_minutes(ts.start))
            weekly[day] = normalized_slots
        model.weekly = weekly
        return model

    class Config:
        str_strip_whitespace = True


class ReviewModel(BaseModel):
    """
    Pydantic model for customer reviews.

    Validates review data structure and content.

    Attributes:
        author_name: Review author name
        rating: Rating value (1-5)
        text: Review text content
        time: Review timestamp (ISO datetime or integer epoch)
        language: Review language code

    Validators:
        validate_rating(): Ensures rating is between 1-5
        validate_language_code(): Validates basic ISO language code forms (2 or 3 letters)
        validate_review_content(): Validates review text content
    """

    author_name: Optional[str] = Field(None, max_length=200, description="Author display name")
    rating: float = Field(..., description="Rating between 1 and 5 inclusive")
    text: Optional[str] = Field(None, description="Review text")
    time: Optional[datetime] = Field(None, description="Timestamp of the review (ISO datetime)")
    language: Optional[str] = Field(None, description="Language code (ISO 639-1 or 639-2, e.g. 'en', 'uk', 'fra')")

    @field_validator("rating")
    def validate_rating(cls, v):
        try:
            fv = float(v)
        except Exception:
            raise ValueError("rating must be numeric")
        if not (1.0 <= fv <= 5.0):
            raise ValueError("rating must be between 1 and 5")
        # keep rating as float if given as float, or int if whole
        if float(int(fv)) == fv:
            return int(fv)
        return fv

    @field_validator("language")
    def validate_language_code(cls, v: Optional[str]) -> Optional[str]:
        """Simple validation: allow 2- or 3-letter alphabetic codes (ISO-like)."""
        if v is None:
            return None
        v = v.strip().lower()
        if not re.match(r"^[a-z]{2,3}$", v):
            raise ValueError("language must be a 2- or 3-letter ISO language code (letters only)")
        return v

    @field_validator("text")
    def validate_review_content(cls, v: Optional[str]) -> Optional[str]:
        """Validate review text length and sanity. Accept empty but trim whitespace."""
        if v is None:
            return None
        text = v.strip()
        if text == "":
            # allow empty review text if needed; choose policy: here we disallow purely empty strings
            raise ValueError("review text cannot be empty")
        if len(text) > 5000:
            raise ValueError("review text too long (max 5000 chars)")
        return text

    @field_validator("time", mode="before")
    def validate_time_field(cls, v):
        if v is None:
            return None
        if isinstance(v, datetime):
            # make timezone-aware (assume UTC if naive)
            if v.tzinfo is None:
                return v.replace(tzinfo=timezone.utc)
            return v
        if isinstance(v, (int, float)):
            # use UTC for epoch seconds
            return datetime.fromtimestamp(int(v), tz=timezone.utc)
        if isinstance(v, str):
            try:
                dt = datetime.fromisoformat(v)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except Exception:
                raise ValueError("time string must be ISO format (YYYY-MM-DDTHH:MM:SS) or epoch int")
        raise ValueError("time must be datetime, ISO string or epoch int")

    @field_serializer("time")
    def serialize_time(self, v: Optional[datetime]):
        """
        Correct serializer signature: (self, value, info).
        Normalize to UTC and emit ISO with microseconds and +00:00 offset.
        """
        if v is None:
            return None
        # ensure timezone-aware then output with microseconds and colon in offset
        v_utc = v.astimezone(timezone.utc)
        # isoformat with microseconds yields 'YYYY-MM-DDTHH:MM:SS.ffffff+00:00'
        return v_utc.isoformat(timespec="microseconds")
    
    class Config:
        anystr_strip_whitespace = True
        schema_extra = {
            "example": {
                "author_name": "Alice",
                "rating": 5,
                "text": "Excellent place, friendly staff!",
                "time": "2023-08-25T00:04:59.000000+00:00",
                "language": "en",
            }
        }


class AttractionModel(BaseModel):
    """
    Complete Pydantic model for attraction data aligned with the provided DB schema.

    Changes from prior sketch:
      - Replaced generic accessibility/service lists with explicit boolean fields found in YAML.
      - Replaced `url` with `maps_url`.
      - `last_updated` aligned to date type per schema.
    """

    name: str = Field(..., description="Attraction name (required)", max_length=300)
    city: str = Field(..., description="City")
    address: str = Field(..., description="Full address string")
    postal_code: str = Field(..., description="Postal/ZIP code")
    administrative_area_level_1: Optional[str] = Field(None, description="State/Province")
    administrative_area_level_2: Optional[str] = Field(None, description="County/District")
    sublocality_level_1: Optional[str] = Field(None, description="Local subdivision")
    coordinates: CoordinatesModel = Field(..., description="Geographic coordinates (lat,lng)")
    place_id: str = Field(..., description="Google Places ID")
    phone_number: Optional[str] = Field(None, description="Contact phone number (normalized)")
    maps_url: str = Field(..., description="Maps / website URL (maps_url)")
    opening_hours: Optional[OpeningHoursModel] = Field(None, description="Opening hours structure")
    price_level: Optional[int] = Field(None, description="Price level (0-4)")
    rating: Optional[float] = Field(None, description="Average rating (0.0 - 5.0)")
    reviews: List[ReviewModel] = Field(default_factory=list, description="List of reviews")
    tags: List[str] = Field(default_factory=list, description="List of category tags")

    # Accessibility / service booleans defined explicitly to match YAML schema
    wheelchair_accessible_entrance: Optional[bool] = Field(False, description="Wheelchair accessible entrance")
    serves_beer: Optional[bool] = Field(False, description="Serves beer")
    serves_breakfast: Optional[bool] = Field(False, description="Serves breakfast")
    serves_brunch: Optional[bool] = Field(False, description="Serves brunch")
    serves_dinner: Optional[bool] = Field(False, description="Serves dinner")
    serves_lunch: Optional[bool] = Field(False, description="Serves lunch")
    serves_vegetarian_food: Optional[bool] = Field(False, description="Serves vegetarian food")
    serves_wine: Optional[bool] = Field(False, description="Serves wine")
    takeout: Optional[bool] = Field(False, description="Takeout available")

    last_updated: datetime = Field(..., description="Last update timestamp (ISO datetime)")

    @field_validator(
        "wheelchair_accessible_entrance",
        "serves_beer",
        "serves_breakfast",
        "serves_brunch",
        "serves_dinner",
        "serves_lunch",
        "serves_vegetarian_food",
        "serves_wine",
        "takeout",
        mode="before",
    )
    def coerce_bool_like(cls, v):
        """Coerce common truthy/falsy representations into booleans."""
        if v is None:
            return False
        if isinstance(v, bool):
            return v
        if isinstance(v, (int, float)):
            return bool(int(v))
        if isinstance(v, str):
            s = v.strip().lower()
            if s in {"1", "true", "yes", "y", "t", "on"}:
                return True
            if s in {"0", "false", "no", "n", "f", "off", ""}:
                return False
        raise ValueError("boolean field must be bool, numeric 0/1, or a truthy/falsey string")

    @field_validator("phone_number")
    def validate_phone_number(cls, v: Optional[str]) -> Optional[str]:
        """Normalize and validate an international-ish phone number (basic)."""
        if v is None:
            return None
        s = v.strip()
        normalized = _PHONE_NORMALIZE_RE.sub("", s)
        if not _PHONE_E164_RE.match(normalized):
            raise ValueError("phone_number must be digits (7-15) and may start with '+'")
        if not normalized.startswith("+"):
            normalized = f"+{normalized}"
        return normalized

    @field_validator("maps_url")
    def validate_maps_url(cls, v: Optional[str]) -> Optional[str]:
        """Basic maps_url validation/normalization (requires http/https or www.)."""
        if v is None:
            return None
        s = v.strip()
        if not _URL_SIMPLE_RE.match(s):
            raise ValueError("maps_url must start with http://, https:// or www.")
        parsed = urlparse(s if "://" in s else f"https://{s}")
        if not parsed.netloc:
            raise ValueError("maps_url appears invalid")
        scheme = parsed.scheme or "https"
        normalized = f"{scheme}://{parsed.netloc}{parsed.path or ''}"
        if parsed.query:
            normalized += f"?{parsed.query}"
        if parsed.fragment:
            normalized += f"#{parsed.fragment}"
        return normalized

    @field_validator("price_level")
    def validate_price_level(cls, v: Optional[int]) -> Optional[int]:
        if v is None:
            return None
        if not isinstance(v, int):
            raise ValueError("price_level must be integer 0..4")
        if not (0 <= v <= 4):
            raise ValueError("price_level must be between 0 and 4")
        return v

    @field_validator("rating")
    def validate_rating_range(cls, v: Optional[Union[int, float]]) -> Optional[Union[int, float]]:
        if v is None:
            return None
        try:
            fv = float(v)
        except Exception:
            raise ValueError("rating must be numeric")
        if not (0.0 <= fv <= 5.0):
            raise ValueError("rating must be between 0.0 and 5.0")
        if math.isclose(fv, int(fv)):
            return int(round(fv))
        return round(fv, 2)

    @field_validator("tags", mode="before")
    def validate_tags_before(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            parts = re.split(r"[;,]", v)
            return [p.strip() for p in parts if p.strip() != ""]
        if isinstance(v, (list, tuple)):
            return list(v)
        raise ValueError("tags must be a list of strings or a comma-separated string")

    @field_validator("tags")
    def validate_tags_after(cls, v: List[str]) -> List[str]:
        normalized: List[str] = []
        seen = set()
        for t in v:
            if t is None:
                continue
            if not isinstance(t, str):
                raise ValueError("each tag must be a string")
            tnorm = t.strip().lower()
            if not tnorm:
                continue
            if not _TAG_RE.match(tnorm):
                raise ValueError(f"invalid tag: '{t}'")
            if tnorm in seen:
                continue
            seen.add(tnorm)
            normalized.append(tnorm)
        return normalized

    @field_validator("reviews", mode="before")
    def ensure_reviews_list(cls, v):
        if v is None:
            return []
        if not isinstance(v, (list, tuple)):
            raise ValueError("reviews must be a list of review objects/dicts")
        return list(v)

    @model_validator(mode="after")
    def validate_required_and_compute(cls, values):
        if not values.name or not values.name.strip():
            raise ValueError("name is required and cannot be empty")
        if values.coordinates is None:
            raise ValueError("coordinates are required")

        # Ensure reviews are ReviewModel objects
        reviews = []
        for r in values.reviews or []:
            if isinstance(r, ReviewModel):
                reviews.append(r)
            elif isinstance(r, dict):
                reviews.append(ReviewModel(**r))
            else:
                raise ValueError("each review must be a ReviewModel or dict")
        values.reviews = reviews

        # Infer rating from reviews if missing
        if values.rating is None and reviews:
            rat_values = []
            for rv in reviews:
                try:
                    rnum = float(rv.rating)
                    if 0.0 <= rnum <= 5.0:
                        rat_values.append(rnum)
                except Exception:
                    continue
            if rat_values:
                avg = sum(rat_values) / len(rat_values)
                values.rating = int(round(avg)) if math.isclose(avg, round(avg)) else round(avg, 2)


        # de-duplicate tags
        values.tags = list(dict.fromkeys(values.tags or []))

        return values

    def to_weaviate_properties(self) -> Dict:
        def serialize_opening_hours(oh):
            if oh is None:
                return None
            oh_dict = oh.model_dump()
            # Convert date objects to strings
            if oh_dict.get('week_start') and hasattr(oh_dict['week_start'], 'isoformat'):
                oh_dict['week_start'] = oh_dict['week_start'].isoformat()
            if oh_dict.get('week_end') and hasattr(oh_dict['week_end'], 'isoformat'):
                oh_dict['week_end'] = oh_dict['week_end'].isoformat()
            return oh_dict
        
        payload = {
            "name": self.name,
            "city": self.city,
            "address": self.address,
            "postal_code": self.postal_code,
            "administrative_area_level_1": self.administrative_area_level_1,
            "administrative_area_level_2": self.administrative_area_level_2,
            "sublocality_level_1": self.sublocality_level_1,
            "coordinates": {"longitude": self.coordinates.longitude, "latitude": self.coordinates.latitude} if self.coordinates else None,
            "place_id": self.place_id,
            "phone_number": self.phone_number,
            "maps_url": self.maps_url,
            "opening_hours": serialize_opening_hours(self.opening_hours) if self.opening_hours else None,
            "price_level": self.price_level,
            "rating": float(self.rating) if self.rating else None,
            "reviews": [r.model_dump() for r in self.reviews],
            "tags": self.tags,
            # explicit boolean fields
            "wheelchair_accessible_entrance": bool(self.wheelchair_accessible_entrance),
            "serves_beer": bool(self.serves_beer),
            "serves_breakfast": bool(self.serves_breakfast),
            "serves_brunch": bool(self.serves_brunch),
            "serves_dinner": bool(self.serves_dinner),
            "serves_lunch": bool(self.serves_lunch),
            "serves_vegetarian_food": bool(self.serves_vegetarian_food),
            "serves_wine": bool(self.serves_wine),
            "takeout": bool(self.takeout),
            "last_updated": self.last_updated if self.last_updated else None,
        }
        return {k: v for k, v in payload.items() if v is not None}

    class Config:
        anystr_strip_whitespace = True
        schema_extra = {
            "example": {
                "name": "Central Park Cafe",
                "city": "New York",
                "coordinates": {"lat": 40.7829, "lng": -73.9654},
                "phone_number": "+12125552368",
                "maps_url": "https://maps.example.com/place/12345",
                "serves_beer": True,
                "serves_breakfast": True,
                "serves_vegetarian_food": True,
                "takeout": False,
                "last_updated": "2025-08-20"
            }
        }


class EmbeddingMetadataModel(BaseModel):
    """
    Pydantic model for embedding metadata.
    
    Validates metadata structure for text embeddings.
    
    Attributes:
        city: City name
        source_file: Original source file name
        chunk_id: Unique chunk identifier
        timestamp: Processing timestamp
        embedding_model: Model used for embedding generation
        cleaning_version: Data cleaning version
        original_length: Original text length
    """
    city: str = Field(..., description="Name of the city where attraction is placed.")
    source_file: str = Field(..., description="Name of the source file with plan text.")
    embedding_model: str = Field(..., description="Name of the embedding model.")
    cleaning_version: str = Field(..., description="Version of the cleaning approach.")
    original_length: int = Field(..., description="Original length of the raw text")
    timestamp: datetime = Field(..., description="ISO 8601 datetime with timezone")

    @field_validator("timestamp", mode="before")
    def _parse_timestamp(cls, v: Union[str, int, float, datetime]):
        # None is not allowed here (Field(...) enforces presence), but handle defensively
        if v is None:
            raise ValueError("timestamp is required")

        # Already a datetime -> use as-is
        if isinstance(v, datetime):
            dt = v
        # Epoch seconds
        elif isinstance(v, (int, float)):
            dt = datetime.fromtimestamp(float(v), tz=timezone.utc)
        # String: try ISO parsing
        elif isinstance(v, str):
            s = v.strip()
            # Python's fromisoformat accepts offsets like +00:00 and microseconds
            try:
                dt = datetime.fromisoformat(s)
            except Exception:
                # Accept trailing 'Z' as UTC
                if s.endswith("Z"):
                    try:
                        dt = datetime.fromisoformat(s[:-1] + "+00:00")
                    except Exception:
                        raise ValueError("timestamp string is not in a supported ISO 8601 format")
                else:
                    raise ValueError("timestamp string is not in a supported ISO 8601 format")
        else:
            raise TypeError("timestamp must be a datetime, ISO string, or epoch number")

        # Ensure timezone-aware: if naive, attach UTC (change to raise if you prefer strictness)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt.isoformat()


class EmbeddingModel(BaseModel):
    """
    Pydantic model for complete embedding data.
    
    Validates text content, vector embedding, and metadata.
    
    Attributes:
        text: Original text content
        embedding: Vector embedding (list of floats)
        metadata: Processing and source metadata
    """
    text: str = Field(..., description="Original text of the embedding")
    embedding: List[float] = Field(..., description="Embedding vector for text")
    metadata: EmbeddingMetadataModel = Field(..., description="Emdedding Metadata model")

