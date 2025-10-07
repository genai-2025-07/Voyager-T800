import asyncio
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, List
import concurrent.futures
from app.services.events.providers.tavily import TavilyEventsProvider
from app.services.events.service import EventsService
from langchain_core.tools import tool
from app.services.weather import WeatherService
from app.services.itinerary.itinerary import ItineraryService

weather_service = WeatherService(project_root=Path(__file__).parent.parent.parent)
itinerary_service = ItineraryService(project_root=Path(__file__).parent.parent.parent)


@dataclass
class WeatherData:
    """Weather data structure"""
    city: str
    date: str
    temp_min: float
    temp_max: float
    description: str
    precipitation: float
    wind_speed: float


def _run_async_in_sync_context(coro):
    """
    Helper function to run async code in a sync context.
    Handles different event loop scenarios.
    
    Args:
        coro: Coroutine to execute
        
    Returns:
        Result from the coroutine
    """
    try:
        # Try to get existing event loop
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If we're in an async context, use run_in_executor
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, coro)
                return future.result()
        else:
            # If no loop is running, use asyncio.run
            return asyncio.run(coro)
    except RuntimeError:
        # Fallback: create new event loop
        return asyncio.run(coro)


@tool
def get_itineraries(query: str, city: str, max_results: int = 5, language: str = "en") -> str:
    """
    Search for places of interest in a city and return detailed information including descriptions from Wikipedia.
    
    Args:
        query: The type of place to search for (e.g., "museum", "restaurant", "park", "attraction")
        city: The city name to search in (e.g., "Paris", "New York", "Tokyo")
        max_results: Maximum number of results to return (default: 5, max: 10)
        language: Language for the search (default: "en")
    
    Returns:
        JSON string with places information including name, address, rating, description, and Wikipedia links
        
    Examples:
        >>> get_itineraries("museum", "Paris", max_results=3)
        >>> get_itineraries("restaurant", "Tokyo", max_results=5, language="ja")
    """
    try:
        # Limit max_results to reasonable bounds
        k = min(max(1, max_results), 10)
        
        # Get places from the service
        places = itinerary_service.get_places(query, city, k, language)
        
        # Convert to serializable format
        result = [place.serialize() for place in places]
        
        return json.dumps(result, indent=2, ensure_ascii=False)
        
    except Exception as e:
        return json.dumps({
            "error": f"Failed to get places information: {str(e)}",
            "query": query,
            "city": city
        })


@tool
def get_weather_forecast(city: str, start_date: str, end_date: Optional[str] = None) -> str:
    """
    Get weather forecast for a city between specified dates.
    
    Args:
        city: The city name (e.g., "Paris", "New York")
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format (optional, defaults to start_date)
    
    Returns:
        JSON string with weather forecast data containing temperature, precipitation, wind speed, etc.
        
    Examples:
        >>> get_weather_forecast("Paris", "2025-10-15")
        >>> get_weather_forecast("New York", "2025-10-15", "2025-10-20")
    """
    try:
        if not end_date:
            end_date = start_date
        
        # Run the async weather service
        weather_data = _run_async_in_sync_context(
            weather_service.get_weather_forecast(city, start_date, end_date)
        )
        
        return json.dumps(weather_data, indent=2)
        
    except Exception as e:
        return json.dumps({"error": f"Failed to get weather forecast: {str(e)}"})


@tool
def get_events(city: str, start_date: str, end_date: Optional[str] = None, categories: Optional[List[str]] = None) -> str:
    """
    Find events like concerts, festivals, and conferences in a specific city within a date range.
    
    Args:
        city: The city to search for events in (e.g., "London", "San Francisco").
        start_date: The start date for the event search, in YYYY-MM-DD format.
        end_date: The optional end date for the event search, in YYYY-MM-DD format. If not provided, defaults to the start_date.
        categories: An optional list of categories to filter events by (e.g., ["Music", "Festival", "Conference", "Theatre"]).
    
    Returns:
        A JSON string containing a list of events with details like name, date, location, and description.
        
    Examples:
        >>> get_events("London", "2025-10-10", "2025-10-12")
        >>> get_events("San Francisco", "2025-11-01", categories=["Conference", "Tech"])
    """
    try:

        try:
            datetime.strptime(start_date, "%Y-%m-%d")
            if end_date:
                datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            return json.dumps({"error": "Invalid date format. Use YYYY-MM-DD."})
        
        if not end_date:
            end_date = start_date


        
        events_service = EventsService(TavilyEventsProvider(project_root=Path(__file__).parent.parent.parent))

        if categories:
            categories = sorted(categories)
        events = events_service.get_events(city, start_date, end_date, categories)

        serialized_events = [event.serialize() for event in events]

        return json.dumps(serialized_events, indent=2)

    except Exception as e:
        return json.dumps({
            "error": f"Failed to get events: {str(e)}",
            "city": city,
            "start_date": start_date
        })