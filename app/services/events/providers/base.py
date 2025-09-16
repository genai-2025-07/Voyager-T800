from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional
from app.services.events.models import Event


class EventsProvider(ABC):
    """
    Abstract base class for event providers.
    
    This class defines the interface that all event providers must implement.
    It ensures consistent behavior across different event data sources (Tavily, 
    Eventbrite, etc.) and allows for easy provider swapping.
    
    All concrete providers should inherit from this class and implement
    the fetch method according to their specific API requirements.
    """
    
    @abstractmethod
    def fetch(self, city: str, start_date: datetime, end_date: datetime, categories: Optional[List[str]] = None) -> List[Event]:
        """
        Fetch events from the provider's data source.
        
        This method must be implemented by all concrete provider classes.
        It should handle the communication with external APIs, data parsing,
        and conversion to Event objects.
        
        Args:
            city: Destination city name (e.g., "Kyiv", "Lviv")
            start_date: Start date for event search (inclusive)
            end_date: End date for event search (inclusive)
            categories: Optional list of event categories to filter by
                       (e.g., ["concerts", "festivals", "cultural events"])
        
        Returns:
            List of Event objects matching the search criteria.
            Should return an empty list if no events are found.
        
        Raises:
            ValidationError: If input parameters are invalid
            RequestException: If API communication fails
            ProviderError: If provider-specific errors occur
            
        Note:
            - Input validation should be handled by the calling service layer
            - All returned events should be valid Event objects
            - Provider should handle API rate limiting and error recovery
            - Consider implementing caching at the provider level if appropriate
        """
        pass