"""
Integration tests for events functionality.

Tests the complete flow from API calls to event injection in itinerary chain.
These tests use real API calls but with controlled test data.
"""
import pytest
from unittest.mock import patch, Mock
from datetime import datetime, date
from app.services.events.service import EventsService
from app.services.events.providers.tavily import TavilyEventsProvider
from app.services.events.models import EventQuery


class TestEventsIntegration:
    """Integration tests for events functionality."""

    @pytest.fixture
    def sample_event_query(self):
        """Sample event query for testing."""
        return EventQuery(
            city="Kyiv",
            start_date=date(2025, 9, 10),
            end_date=date(2025, 9, 15),
            categories=["music", "food"]
        )

    @pytest.fixture
    def sample_events_data(self):
        """Sample events data that would be returned by Tavily API."""
        return [
            {
                "title": "Kyiv Music Festival",
                "category": "Music",
                "date": "2025-09-12T18:00:00",
                "venue": "Maidan Nezalezhnosti",
                "url": "https://example.com/event1"
            },
            {
                "title": "Food & Wine Expo",
                "category": "Food",
                "date": "2025-09-13T12:00:00",
                "venue": "Expo Center",
                "url": "https://example.com/event2"
            }
        ]

    @pytest.fixture
    def mock_tavily_response(self, sample_events_data):
        """Mock Tavily API response for integration tests."""
        import json
        return {
            "answer": f"""
            Here are some events in Kyiv:
            ```json
            {json.dumps(sample_events_data)}
            ```
            """
        }

    @patch('requests.post')
    @patch.dict('os.environ', {'TAVILY_API_KEY': 'test_api_key'})
    def test_tavily_provider_integration(self, mock_post, mock_tavily_response, sample_events_data):
        """Test integration with Tavily API provider."""
        mock_response = Mock()
        mock_response.json.return_value = mock_tavily_response
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        provider = TavilyEventsProvider()
        service = EventsService(provider)

        city = "Kyiv"
        start_date = datetime(2025, 9, 10)
        end_date = datetime(2025, 9, 15)
        categories = ["music", "food"]

        events = service.get_events(city, start_date, end_date, categories)

        assert len(events) == 2
        assert events[0].title == "Kyiv Music Festival"
        assert events[0].category == "Music"
        assert events[1].title == "Food & Wine Expo"
        assert events[1].category == "Food"

        # Verify API call was made
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert "query" in call_args[1]["json"]
        assert call_args[1]["json"]["country"] == "ukraine"

    def test_get_events_for_itinerary_integration(self, sample_event_query, sample_events_data):
        """Test the get_events_for_itinerary method used in the itinerary chain."""

        from app.services.events.models import Event
        mock_events = [
            Event(**event_data) for event_data in sample_events_data
        ]
 
        mock_provider = Mock()
        mock_provider.fetch.return_value = mock_events
        
        service = EventsService(mock_provider)

        result = service.get_events_for_itinerary(sample_event_query)

        assert isinstance(result, dict)
        assert "Day 3" in result  # 2025-09-12 is 3 days after 2025-09-10
        assert "Day 4" in result  # 2025-09-13 is 4 days after 2025-09-10
        assert "evening" in result["Day 3"]
        assert "afternoon" in result["Day 4"]
        
        # Check event data structure
        evening_events = result["Day 3"]["evening"]
        afternoon_events = result["Day 4"]["afternoon"]
        
        assert len(evening_events) == 1
        assert len(afternoon_events) == 1
        assert evening_events[0]["title"] == "Kyiv Music Festival"
        assert afternoon_events[0]["title"] == "Food & Wine Expo"

        # Verify provider was called with correct parameters
        mock_provider.fetch.assert_called_once_with(
            "Kyiv",
            datetime(2025, 9, 10, 0, 0),  # date converted to datetime.min.time()
            datetime(2025, 9, 15, 0, 0),  # date converted to datetime.min.time() (Pydantic default)
            ["music", "food"]
        )

    def test_get_events_for_itinerary_empty_query(self):
        """Test get_events_for_itinerary with empty or invalid event query."""

        service = EventsService(Mock())

        result = service.get_events_for_itinerary(None)

        assert result is None

    def test_get_events_for_itinerary_no_events_found(self, sample_event_query):
        """Test get_events_for_itinerary when no events are found."""

        mock_provider = Mock()
        mock_provider.fetch.return_value = []
        service = EventsService(mock_provider)

        result = service.get_events_for_itinerary(sample_event_query)

        assert result == {}

    def test_get_events_for_itinerary_with_none_categories(self, sample_events_data):
        """Test get_events_for_itinerary with None categories."""

        from app.services.events.models import Event
        mock_events = [
            Event(**event_data) for event_data in sample_events_data
        ]
        
        mock_provider = Mock()
        mock_provider.fetch.return_value = mock_events
        service = EventsService(mock_provider)

        event_query = EventQuery(
            city="Kyiv",
            start_date=date(2025, 9, 10),
            end_date=date(2025, 9, 15)
            # categories will default to ["events"]
        )

        result = service.get_events_for_itinerary(event_query)

        assert isinstance(result, dict)
        assert "Day 3" in result
        assert "evening" in result["Day 3"]

        # Verify service was called with default categories
        mock_provider.fetch.assert_called_once_with(
            "Kyiv",
            datetime(2025, 9, 10, 0, 0),  # date converted to datetime.min.time()
            datetime(2025, 9, 15, 0, 0),  # date converted to datetime.min.time()  
            ["events"]  # default categories
        )

    def test_get_events_for_itinerary_service_exception(self, sample_event_query):
        """Test get_events_for_itinerary when service raises an exception."""

        mock_provider = Mock()
        mock_provider.fetch.side_effect = Exception("Service error")
        service = EventsService(mock_provider)

        result = service.get_events_for_itinerary(sample_event_query)

        assert result is None

    def test_events_service_with_cache_integration(self, sample_events_data):
        """Test EventsService with cache integration."""
        from app.services.events.models import Event
        mock_events = [
            Event(**event_data) for event_data in sample_events_data
        ]

        mock_provider = Mock()
        mock_provider.fetch.return_value = mock_events

        mock_cache = Mock()
        mock_cache.get.return_value = None  # Cache miss
        mock_cache.set.return_value = None

        service = EventsService(mock_provider, mock_cache)

        city = "Kyiv"
        start_date = datetime(2025, 9, 10)
        end_date = datetime(2025, 9, 15)
        categories = ["music", "food"]

        events = service.get_events(city, start_date, end_date, categories)

        assert len(events) == 2
        assert events[0].title == "Kyiv Music Festival"

        # Verify cache interactions
        mock_cache.get.assert_called_once()
        mock_cache.set.assert_called_once()
        mock_provider.fetch.assert_called_once()

    def test_events_service_cache_hit_integration(self, sample_events_data):
        """Test EventsService with cache hit."""
        from app.services.events.models import Event
        cached_events = [
            Event(**event_data) for event_data in sample_events_data
        ]

        mock_provider = Mock()

        mock_cache = Mock()
        mock_cache.get.return_value = cached_events

        service = EventsService(mock_provider, mock_cache)

        city = "Kyiv"
        start_date = datetime(2025, 9, 10)
        end_date = datetime(2025, 9, 15)
        categories = ["music", "food"]

        events = service.get_events(city, start_date, end_date, categories)

        assert len(events) == 2
        assert events[0].title == "Kyiv Music Festival"

        # Verify cache hit
        mock_cache.get.assert_called_once()
        mock_cache.set.assert_not_called()
        mock_provider.fetch.assert_not_called()

    @patch('requests.post')
    @patch.dict('os.environ', {'TAVILY_API_KEY': 'test_api_key'})
    def test_end_to_end_events_flow(self, mock_post, mock_tavily_response, sample_events_data):
        """Test complete end-to-end flow from API to itinerary mapping."""

        mock_response = Mock()
        mock_response.json.return_value = mock_tavily_response
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        # Create real service with mocked API
        provider = TavilyEventsProvider()
        service = EventsService(provider)

        event_query = EventQuery(
            city="Kyiv",
            start_date=date(2025, 9, 10),
            end_date=date(2025, 9, 15),
            categories=["music", "food"]
        )

        result = service.get_events_for_itinerary(event_query)

        assert isinstance(result, dict)
        assert "Day 3" in result  # 2025-09-12 is 3 days after 2025-09-10
        assert "Day 4" in result  # 2025-09-13 is 4 days after 2025-09-10
        assert "evening" in result["Day 3"]
        assert "afternoon" in result["Day 4"]
        
        # Check specific event data
        evening_event = result["Day 3"]["evening"][0]
        afternoon_event = result["Day 4"]["afternoon"][0]
        
        assert evening_event["title"] == "Kyiv Music Festival"
        assert evening_event["venue"] == "Maidan Nezalezhnosti"
        assert evening_event["url"] == "https://example.com/event1"
        assert evening_event["date"] == "2025-09-12"
        
        assert afternoon_event["title"] == "Food & Wine Expo"
        assert afternoon_event["venue"] == "Expo Center"
        assert afternoon_event["url"] == "https://example.com/event2"
        assert afternoon_event["date"] == "2025-09-13"

        # Verify API was called
        mock_post.assert_called_once()

