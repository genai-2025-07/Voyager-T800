import os
import logging
import requests
from datetime import datetime
from typing import List, Optional
from app.services.events.models import Event, EventRequest
from app.services.events.providers.base import EventsProvider
from app.utils.events_utils import extract_events, build_query

logger = logging.getLogger(__name__)


class TavilyEventsProvider(EventsProvider):
    """
    Tavily API provider for fetching events.

    Handles API communication with Tavily search service to retrieve event data.
    Includes comprehensive error handling and validation.
    """

    def __init__(self):
        """Initialize the Tavily provider with API configuration."""
        logger.info("Initializing TavilyEventsProvider")

        try:
            self.api_key = os.getenv("TAVILY_API_KEY")
            if not self.api_key or not self.api_key.strip():
                raise ValueError("TAVILY_API_KEY environment variable is not set or empty")
            
            self.api_url = os.getenv("TAVILY_API_URL", "https://api.tavily.com/search")

            logger.info("TavilyEventsProvider initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize TavilyEventsProvider: {e}")
            raise

    def fetch(
        self,
        city: str,
        start_date: datetime,
        end_date: datetime,
        categories: Optional[List[str]] = None,
    ) -> List[Event]:
        """
        Fetch events from Tavily API.

        Args:
            city: Destination city name
            start_date: Start date for event search
            end_date: End date for event search
            categories: List of event categories to search for

        Returns:
            List of Event objects

        Raises:
            ValidationError: If input parameters are invalid (from Pydantic)
            requests.RequestException: If API request fails
            KeyError: If API response format is unexpected
        """
        logger.info(
            f"Fetching events for city: {city}, date range: {start_date} to {end_date}, categories: {categories}"
        )

        try:
            # Validate input using Pydantic model
            request = EventRequest(
                city=city,
                start_date=start_date,
                end_date=end_date,
                categories=categories,
            )
            logger.debug("Input validation passed")

            # Build query using events utils
            logger.debug("Building query string")
            query = build_query(
                request.city,
                request.start_date,
                request.end_date,
                request.categories or [],
            )
            logger.debug(f"Query built successfully, length: {len(query)}")

            # Prepare API request
            request_payload = {
                "query": query,
                "include_answer": "advanced",
                "country": "ukraine",
                "max_results": 5,
            }

            headers = {"Authorization": f"Bearer {self.api_key}"}

            logger.debug(f"Making API request to {self.api_url}")

            # Make API request with timeout
            response = requests.post(
                self.api_url, headers=headers, json=request_payload, timeout=30
            )

            logger.debug(f"API response status: {response.status_code}")

            # Check for HTTP errors
            response.raise_for_status()

            # Parse response
            response_data = response.json()
            logger.debug(f"API response received, keys: {list(response_data.keys())}")

            # Extract answer from response
            raw_answer = response_data.get("answer", "")
            if not raw_answer:
                logger.warning("Empty answer received from Tavily API")
                return []

            # Extract events from raw answer
            parsed_events = extract_events(raw_answer)
            logger.debug(f"Successfully extracted {len(parsed_events)} events")

            # Convert to Event objects
            events = []
            for i, event_data in enumerate(parsed_events):
                try:
                    event = Event(**event_data)
                    events.append(event)
                    logger.debug(f"Successfully created event {i+1}: {event.title}")
                except Exception as e:
                    logger.warning(
                        f"Failed to create event {i+1} from data {event_data}: {e}"
                    )
                    continue

            logger.info(f"Successfully created {len(events)} Event objects")
            return events

        except requests.exceptions.Timeout as e:
            logger.error(f"API request timeout: {e}")
            raise requests.RequestException(f"Tavily API request timed out: {e}")
        except requests.exceptions.ConnectionError as e:
            logger.error(f"API connection error: {e}")
            raise requests.RequestException(f"Failed to connect to Tavily API: {e}")
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error from Tavily API: {e}")
            raise requests.RequestException(f"Tavily API HTTP error: {e}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error: {e}")
            raise requests.RequestException(f"Tavily API request failed: {e}")
        except KeyError as e:
            logger.error(f"Unexpected API response format: {e}")
            raise KeyError(f"Unexpected response format from Tavily API: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in fetch: {e}")
            raise
