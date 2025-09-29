## Events Module Documentation

This document explains the Events subsystem: data models, service API, provider integration, configuration, usage examples, and sample outputs. It is intended for developers consuming the events functionality from within the backend or during itinerary generation.

### Overview

- **Purpose**: Find city events for a date range and map them into itinerary-friendly day/time slots.
- **Architecture**: A thin service layer (`app/services/events/service.py`) calls a pluggable provider (`app/services/events/providers/*`).
- **Models**: Strict validation via Pydantic ensures predictable shapes.

### Data Models

- **`Event`** (`app/services/events/models.py`)
  - Fields: `title: str`, `category: str`, `date: datetime`, `venue: str`, `url: str`
  - Validation: non-empty strings; `url` must start with `http://` or `https://`.

- **`EventQuery`** (input parsed from higher-level user intent)
  - Fields: `city: str`, `start_date: Optional[date]`, `end_date: Optional[date]`, `categories: List[str]` (defaults to `["events"]`)
  - Notes: gracefully accepts `""`/`"null"`/`None` for dates.

- **`EventRequest`** (validated request to providers)
  - Fields: `city: str`, `start_date: datetime`, `end_date: datetime`, `categories: Optional[List[str]]`
  - Validation: `end_date` must be after `start_date`; categories must be a list of non-empty strings if provided.

### Service API

Located at `app/services/events/service.py`.

- **`EventsService(provider: EventsProvider, cache: Optional[Any] = None)`**
  - Orchestrates validation, caching, and provider calls.

- **`get_events(city: str, start_date: datetime, end_date: datetime, categories: Optional[List[str]] = None) -> List[Event]`**
  - Validates input using `EventRequest`.
  - Uses an optional cache with key: `"{city}-{start_date}-{end_date}-{categories or 'all'}"`.
  - Calls `provider.fetch(...)` and returns up to 10 events.
  - Raises provider/validation exceptions to caller.

- **`get_events_for_itinerary(event_query: EventQuery) -> Dict[str, dict] | None`**
  - Returns events mapped to days and time slots: morning [8–12), afternoon [12–17), evening [17–23).
  - Skips events outside those hours.
  - Returns `None` if dates are missing/invalid or on errors.

### Provider Interface and Implementations

- **`EventsProvider`** (`app/services/events/providers/base.py`)
  - Abstract `fetch(city, start_date, end_date, categories) -> List[Event]`.

- **`TavilyEventsProvider`** (`app/services/events/providers/tavily.py`)
  - Uses Tavily Search API to retrieve candidate event data and converts to `Event`.
  - Relies on `app/utils/events_utils.py` for `build_query` and `extract_events`.

### Configuration

Environment variables required by `TavilyEventsProvider`:

- `TAVILY_API_KEY`: required
- `TAVILY_API_URL`: optional, defaults to `https://api.tavily.com/search`

Ensure these are provided via secure environment configuration. Do not hardcode secrets.

### Python Usage Examples

Instantiate the service with the Tavily provider and fetch events:

```python
from datetime import datetime
from app.services.events.service import EventsService
from app.services.events.providers.tavily import TavilyEventsProvider

provider = TavilyEventsProvider()
service = EventsService(provider)

events = service.get_events(
    city="Kyiv",
    start_date=datetime(2025, 9, 10),
    end_date=datetime(2025, 9, 15),
    categories=["music", "food"],
)
```

Map events into itinerary-friendly blocks using an `EventQuery`-like object:

```python
from datetime import datetime
from app.services.events.service import EventsService
from app.services.events.providers.tavily import TavilyEventsProvider

provider = TavilyEventsProvider()
service = EventsService(provider)

class SimpleQuery:
    city = "Kyiv"
    start_date = datetime(2025, 9, 10)
    end_date = datetime(2025, 9, 15)
    categories = ["music", "culture"]

itinerary_events = service.get_events_for_itinerary(SimpleQuery)
```

With an in-memory cache:

```python
class SimpleCache:
    def __init__(self):
        self.data = {}
    def get(self, key):
        return self.data.get(key)
    def set(self, key, value):
        self.data[key] = value

service = EventsService(TavilyEventsProvider(), cache=SimpleCache())
```

### Sample Outputs

- **List of events** (return value of `get_events`):

```json
[
  {
    "title": "Test Event 1",
    "category": "Music",
    "date": "2025-09-12T18:00:00",
    "venue": "Test Venue 1",
    "url": "https://example.com/event1"
  },
  {
    "title": "Test Event 2",
    "category": "Food",
    "date": "2025-09-13T12:00:00",
    "venue": "Test Venue 2",
    "url": "https://example.com/event2"
  }
]
```

- **Itinerary mapping** (return value of `get_events_for_itinerary`):

```json
{
  "Day 1": {
    "afternoon": [
      {
        "title": "Lunch Event",
        "category": "Food",
        "time": "14:00",
        "date": "2025-09-12",
        "venue": "Restaurant",
        "url": "https://example.com/lunch"
      }
    ],
    "evening": [
      {
        "title": "Night Concert",
        "category": "Music",
        "time": "20:30",
        "date": "2025-09-12",
        "venue": "Concert Hall",
        "url": "https://example.com/night"
      }
    ]
  },
  "Day 2": {
    "morning": [
      {
        "title": "Breakfast Event",
        "category": "Food",
        "time": "09:00",
        "date": "2025-09-13",
        "venue": "Cafe",
        "url": "https://example.com/breakfast"
      }
    ]
  }
}
```

### Error Handling

- Provider-related HTTP errors are surfaced as `requests.RequestException` (timeout, connection, HTTP errors).
- Validation issues (invalid city, date ranges, malformed categories) raise `ValueError` from Pydantic validators.
- `get_events_for_itinerary` returns `None` on missing dates or when an exception occurs.

### Testing Notes

- Unit tests live in `tests/services/events/` and follow AAA and mocking guidelines.
- See in particular:
  - `test_events_service.py` for service behavior, caching, and mapping logic
  - `test_events_tavily_provider.py` for provider specifics and error handling
  - `test_itinerary_events_injection.py` for integration with itinerary mapping

### Current Limitations and Extensions

- No public FastAPI endpoint is exposed yet; the service is consumed internally. If an HTTP API is required, expose a thin endpoint that validates input with Pydantic and delegates to `EventsService`.
- Additional providers (e.g., Eventbrite) can be added by implementing `EventsProvider`.


