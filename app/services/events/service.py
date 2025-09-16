import logging
from typing import List, Optional, Dict
from datetime import datetime
from .models import Event, EventRequest
from .providers.base import EventsProvider

logger = logging.getLogger(__name__)


class EventsService:
    """
    Service layer for event management.

    Handles caching, validation, and coordinates with event providers.
    """

    def __init__(self, provider: EventsProvider, cache=None):
        """
        Initialize the events service.

        Args:
            provider: Event provider implementation
            cache: Optional cache implementation for storing results
        """
        self.provider = provider
        self.cache = cache

    def get_events(
        self, city: str, start_date, end_date, categories: Optional[List[str]] = None
    ) -> List[Event]:
        """
        Get events for a given city and date range.

        Args:
            city: Destination city name
            start_date: Start date for event search
            end_date: End date for event search
            categories: List of event categories to search for

        Returns:
            List of Event objects (limited to 10 results)

        Raises:
            ValidationError: If input parameters are invalid (from Pydantic)
            ProviderError: If the event provider fails
        """
        logger.info(
            f"Getting events for city: {city}, date range: {start_date} to {end_date}, categories: {categories}"
        )

        try:
            # Validate input using Pydantic model
            request = EventRequest(
                city=city,
                start_date=start_date,
                end_date=end_date,
                categories=categories,
            )

            # Check cache first
            cache_key = f"{request.city}-{request.start_date}-{request.end_date}-{request.categories or 'all'}"
            if self.cache:
                cached_events = self.cache.get(cache_key)
                if cached_events:
                    return cached_events
                logger.debug("Cache miss: fetching from provider")

            # Fetch events from provider
            logger.debug("Fetching events from provider")
            events = self.provider.fetch(
                request.city, request.start_date, request.end_date, request.categories
            )
            logger.info(f"Provider returned {len(events)} events")

            # Limit results to 10
            limited_events = events[:10]
            logger.info(f"Returning {len(limited_events)} events (limited to 10)")

            # Cache the results
            if self.cache:
                logger.debug("Caching results")
                self.cache.set(cache_key, limited_events)

            return limited_events

        except Exception as e:
            logger.error(f"Failed to get events: {e}")
            raise

    def _map_events_with_day_and_timeslot(
        self, events: List[Event], start_date: datetime.date
    ) -> Dict[str, dict]:
        """
        Map events to itinerary in the format:
        {
          "Day 1": { "afternoon": [ {...}, {...} ] },
          "Day 2": { "evening": [ {...} ] }
        }

        - Uses "Day N" based on difference from `start_date`
        - Skips empty blocks (only include blocks with events)
        """
        mapped = {}

        for e in events:
            event_date = e.date.date()
            day_index = (event_date - start_date).days + 1
            day_key = f"Day {day_index}"
            hour = e.date.hour
            if 8 <= hour < 12:
                block = "morning"
            elif 12 <= hour < 17:
                block = "afternoon"
            elif 17 <= hour < 23:
                block = "evening"
            else:
                # Skip events outside itinerary range (night, early morning, etc.)
                continue

            if day_key not in mapped:
                mapped[day_key] = {}

            if block not in mapped[day_key]:
                mapped[day_key][block] = []

            mapped[day_key][block].append(
                {
                    "title": e.title,
                    "category": e.category,
                    "time": e.date.strftime("%H:%M"),
                    "date": event_date.isoformat(),
                    "venue": e.venue,
                    "url": e.url,
                }
            )

        return mapped

    def get_events_for_itinerary(self, event_query: "EventQuery") -> Dict[str, dict] | None:  # type: ignore
        """
        Get events and map them to itinerary format.

        Args:
            event_query: EventQuery object with search parameters

        Returns:
            Dict mapping days to time blocks with events, or None if no events/error
        """
        if (
            not event_query
            or not event_query.start_date
            or not event_query.end_date
            or event_query.start_date == ""
            or event_query.end_date == ""
        ):
            return None

        try:
            start_date = event_query.start_date
            if hasattr(start_date, "date"):
                start_date = start_date.date()

            raw_events = self.get_events(
                event_query.city,
                event_query.start_date,
                event_query.end_date,
                event_query.categories or [],
            )
            return self._map_events_with_day_and_timeslot(raw_events, start_date)
        except (ValueError, TypeError) as e:
            logger.warning(
                f"Failed to get events due to validation error, continuing without events: {e}"
            )
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting events for itinerary: {e}")
            return None
