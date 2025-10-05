"""
Unit tests for EventsService.

Tests the service layer that orchestrates event providers and caching.
"""
import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from pathlib import Path
from app.services.events.service import EventsService
from app.services.events.models import Event
from app.services.events.providers.base import EventsProvider
from app.services.events.providers.tavily import TavilyEventsProvider
from app.agents.tools import get_events


class MockEventsProvider(EventsProvider):
    """Mock implementation of EventsProvider for testing."""
    
    def __init__(self, events_to_return=None):
        self.events_to_return = events_to_return or []
        self.fetch_calls = []
    
    def fetch(self, city: str, start_date: datetime, end_date: datetime, categories: list[str] = None):
        self.fetch_calls.append({
            'city': city,
            'start_date': start_date,
            'end_date': end_date,
            'categories': categories
        })
        return self.events_to_return


class MockCache:
    """Mock cache implementation for testing."""
    
    def __init__(self):
        self.data = {}
        self.get_calls = []
        self.set_calls = []
    
    def get(self, key):
        self.get_calls.append(key)
        return self.data.get(key)
    
    def set(self, key, value):
        self.set_calls.append((key, value))
        self.data[key] = value


class TestEventsService:
    """Test cases for EventsService."""

    @pytest.fixture
    def sample_events(self):
        """Sample events for testing."""
        return [
            Event(
                title="Test Event 1",
                category="Music",
                date=datetime(2025, 9, 12, 18, 0),
                venue="Test Venue 1",
                url="https://example.com/event1"
            ),
            Event(
                title="Test Event 2",
                category="Food",
                date=datetime(2025, 9, 13, 12, 0),
                venue="Test Venue 2",
                url="https://example.com/event2"
            )
        ]

    def test_service_initialization_without_cache(self):
        """Test service initialization without cache."""
        provider = MockEventsProvider()
        service = EventsService(provider)
        
        assert service.provider == provider
        assert service.cache is None

    def test_service_initialization_with_cache(self):
        """Test service initialization with cache."""
        provider = MockEventsProvider()
        cache = MockCache()
        service = EventsService(provider, cache)
        
        assert service.provider == provider
        assert service.cache == cache

    def test_get_events_no_cache(self, sample_events):
        """Test getting events without cache."""

        provider = MockEventsProvider(sample_events)
        service = EventsService(provider)
        
        city = "Kyiv"
        start_date = datetime(2025, 9, 10)
        end_date = datetime(2025, 9, 15)
        categories = ["music", "food"]

        # Act
        events = service.get_events(city, start_date, end_date, categories)

        # Assert
        assert events == sample_events
        assert len(provider.fetch_calls) == 1
        assert provider.fetch_calls[0]['city'] == city
        assert provider.fetch_calls[0]['start_date'] == start_date
        assert provider.fetch_calls[0]['end_date'] == end_date
        assert provider.fetch_calls[0]['categories'] == categories

    def test_get_events_with_cache_hit(self, sample_events):
        """Test getting events with cache hit."""

        provider = MockEventsProvider(sample_events)
        cache = MockCache()
        service = EventsService(provider, cache)
        
        city = "Kyiv"
        start_date = datetime(2025, 9, 10)
        end_date = datetime(2025, 9, 15)
        categories = ["music", "food"]
        
        # Pre-populate cache
        cache_key = f"{city}-{start_date}-{end_date}-{sorted(categories)}"
        cache.set(cache_key, sample_events)

        # Act
        events = service.get_events(city, start_date, end_date, categories)

        # Assert
        assert events == sample_events
        assert len(provider.fetch_calls) == 0  # Should not call provider
        assert len(cache.get_calls) == 1
        assert cache.get_calls[0] == cache_key

    def test_get_events_with_cache_miss(self, sample_events):
        """Test getting events with cache miss."""

        provider = MockEventsProvider(sample_events)
        cache = MockCache()
        service = EventsService(provider, cache)
        
        city = "Kyiv"
        start_date = datetime(2025, 9, 10)
        end_date = datetime(2025, 9, 15)
        categories = ["food", "music"]

        # Act
        events = service.get_events(city, start_date, end_date, categories)

        # Assert
        assert events == sample_events
        assert len(provider.fetch_calls) == 1
        assert len(cache.get_calls) == 1
        assert len(cache.set_calls) == 1
        assert cache.set_calls[0][0] == f"{city}-{start_date}-{end_date}-{sorted(categories)}"
        assert cache.set_calls[0][1] == sample_events

    def test_get_events_limits_results(self):
        """Test that service limits results to 10 events."""

        many_events = [
            Event(
                title=f"Event {i}",
                category="Music",
                date=datetime(2025, 9, 12, 18, 0),
                venue=f"Venue {i}",
                url=f"https://example.com/event{i}"
            )
            for i in range(15)  # More than 10 events
        ]
        provider = MockEventsProvider(many_events)
        service = EventsService(provider)
        
        city = "Kyiv"
        start_date = datetime(2025, 9, 10)
        end_date = datetime(2025, 9, 15)

        # Act
        events = service.get_events(city, start_date, end_date)

        # Assert
        assert len(events) == 10
        assert events == many_events[:10]

    def test_get_events_with_none_categories(self, sample_events):
        """Test getting events with None categories."""

        provider = MockEventsProvider(sample_events)
        service = EventsService(provider)
        
        city = "Kyiv"
        start_date = datetime(2025, 9, 10)
        end_date = datetime(2025, 9, 15)

        # Act
        events = service.get_events(city, start_date, end_date, categories=None)

        # Assert
        assert events == sample_events
        assert len(provider.fetch_calls) == 1
        assert provider.fetch_calls[0]['categories'] is None

    def test_get_events_with_empty_categories(self, sample_events):
        """Test getting events with empty categories list."""

        provider = MockEventsProvider(sample_events)
        service = EventsService(provider)
        
        city = "Kyiv"
        start_date = datetime(2025, 9, 10)
        end_date = datetime(2025, 9, 15)

        # Act
        events = service.get_events(city, start_date, end_date, categories=[])

        # Assert
        assert events == sample_events
        assert len(provider.fetch_calls) == 1
        assert provider.fetch_calls[0]['categories'] == []

    def test_get_events_provider_exception(self):
        """Test handling of provider exceptions."""
        # Arrange
        provider = MockEventsProvider()
        provider.fetch = Mock(side_effect=Exception("Provider error"))
        service = EventsService(provider)
        
        city = "Kyiv"
        start_date = datetime(2025, 9, 10)
        end_date = datetime(2025, 9, 15)


        with pytest.raises(Exception, match="Provider error"):
            service.get_events(city, start_date, end_date)

    def test_cache_key_generation(self, sample_events):
        """Test that cache key is generated correctly."""
        # Arrange
        provider = MockEventsProvider(sample_events)
        cache = MockCache()
        service = EventsService(provider, cache)
        
        city = "Kyiv"
        start_date = datetime(2025, 9, 10)
        end_date = datetime(2025, 9, 15)

        # Act
        service.get_events(city, start_date, end_date)

        # Assert
        expected_key = f"{city}-{start_date}-{end_date}-[]"  # None categories becomes empty list []
        assert len(cache.set_calls) == 1
        assert cache.set_calls[0][0] == expected_key

    def test_map_events_with_day_and_timeslot_morning_events(self):
        """Test mapping morning events to itinerary format."""

        events = [
            Event(
                title="Morning Concert",
                category="Music",
                date=datetime(2025, 9, 12, 10, 30),  # 10:30 AM
                venue="Concert Hall",
                url="https://example.com/morning"
            ),
            Event(
                title="Breakfast Event",
                category="Food",
                date=datetime(2025, 9, 12, 9, 0),  # 9:00 AM
                venue="Cafe",
                url="https://example.com/breakfast"
            )
        ]
        start_date = datetime(2025, 9, 12).date()
        service = EventsService(MockEventsProvider())

        result = service._map_events_with_day_and_timeslot(events, start_date)

        assert "Day 1" in result
        assert "morning" in result["Day 1"]
        assert len(result["Day 1"]["morning"]) == 2
        assert result["Day 1"]["morning"][0]["title"] == "Morning Concert"
        assert result["Day 1"]["morning"][1]["title"] == "Breakfast Event"

    def test_map_events_with_day_and_timeslot_afternoon_events(self):
        """Test mapping afternoon events to itinerary format."""
        events = [
            Event(
                title="Lunch Event",
                category="Food",
                date=datetime(2025, 9, 12, 14, 0),  # 2:00 PM
                venue="Restaurant",
                url="https://example.com/lunch"
            ),
            Event(
                title="Art Exhibition",
                category="Culture",
                date=datetime(2025, 9, 12, 15, 30),  # 3:30 PM
                venue="Gallery",
                url="https://example.com/art"
            )
        ]
        start_date = datetime(2025, 9, 12).date()
        service = EventsService(MockEventsProvider())

        result = service._map_events_with_day_and_timeslot(events, start_date)

        assert "Day 1" in result
        assert "afternoon" in result["Day 1"]
        assert len(result["Day 1"]["afternoon"]) == 2
        assert result["Day 1"]["afternoon"][0]["title"] == "Lunch Event"
        assert result["Day 1"]["afternoon"][1]["title"] == "Art Exhibition"

    def test_map_events_with_day_and_timeslot_evening_events(self):
        """Test mapping evening events to itinerary format."""

        events = [
            Event(
                title="Dinner Event",
                category="Food",
                date=datetime(2025, 9, 12, 19, 0),  # 7:00 PM
                venue="Restaurant",
                url="https://example.com/dinner"
            ),
            Event(
                title="Night Concert",
                category="Music",
                date=datetime(2025, 9, 12, 20, 30),  # 8:30 PM
                venue="Concert Hall",
                url="https://example.com/night"
            )
        ]
        start_date = datetime(2025, 9, 12).date()
        service = EventsService(MockEventsProvider())

        result = service._map_events_with_day_and_timeslot(events, start_date)

        assert "Day 1" in result
        assert "evening" in result["Day 1"]
        assert len(result["Day 1"]["evening"]) == 2
        assert result["Day 1"]["evening"][0]["title"] == "Dinner Event"
        assert result["Day 1"]["evening"][1]["title"] == "Night Concert"

    def test_map_events_with_day_and_timeslot_skips_outside_hours(self):
        """Test that events outside 8-23 hour range are skipped."""

        events = [
            Event(
                title="Late Night Event",
                category="Music",
                date=datetime(2025, 9, 12, 23, 30),  # 11:30 PM - should be skipped
                venue="Club",
                url="https://example.com/late"
            ),
            Event(
                title="Early Morning Event",
                category="Food",
                date=datetime(2025, 9, 12, 6, 0),  # 6:00 AM - should be skipped
                venue="Cafe",
                url="https://example.com/early"
            ),
            Event(
                title="Valid Event",
                category="Music",
                date=datetime(2025, 9, 12, 14, 0),  # 2:00 PM - should be included
                venue="Hall",
                url="https://example.com/valid"
            )
        ]
        start_date = datetime(2025, 9, 12).date()
        service = EventsService(MockEventsProvider())

        result = service._map_events_with_day_and_timeslot(events, start_date)

        assert "Day 1" in result
        assert "afternoon" in result["Day 1"]
        assert len(result["Day 1"]["afternoon"]) == 1
        assert result["Day 1"]["afternoon"][0]["title"] == "Valid Event"

    def test_map_events_with_day_and_timeslot_multiple_days(self):
        """Test mapping events across multiple days."""

        events = [
            Event(
                title="Day 1 Event",
                category="Music",
                date=datetime(2025, 9, 12, 14, 0),  # Day 1
                venue="Hall 1",
                url="https://example.com/day1"
            ),
            Event(
                title="Day 2 Event",
                category="Food",
                date=datetime(2025, 9, 13, 14, 0),  # Day 2
                venue="Hall 2",
                url="https://example.com/day2"
            ),
            Event(
                title="Day 3 Event",
                category="Culture",
                date=datetime(2025, 9, 14, 14, 0),  # Day 3
                venue="Hall 3",
                url="https://example.com/day3"
            )
        ]
        start_date = datetime(2025, 9, 12).date()
        service = EventsService(MockEventsProvider())

        result = service._map_events_with_day_and_timeslot(events, start_date)

        assert "Day 1" in result
        assert "Day 2" in result
        assert "Day 3" in result
        assert result["Day 1"]["afternoon"][0]["title"] == "Day 1 Event"
        assert result["Day 2"]["afternoon"][0]["title"] == "Day 2 Event"
        assert result["Day 3"]["afternoon"][0]["title"] == "Day 3 Event"

    def test_map_events_with_day_and_timeslot_event_structure(self):
        """Test that mapped events have correct structure."""

        events = [
            Event(
                title="Test Event",
                category="Music",
                date=datetime(2025, 9, 12, 14, 30),
                venue="Test Venue",
                url="https://example.com/test"
            )
        ]
        start_date = datetime(2025, 9, 12).date()
        service = EventsService(MockEventsProvider())

        result = service._map_events_with_day_and_timeslot(events, start_date)

        event_data = result["Day 1"]["afternoon"][0]
        assert event_data["title"] == "Test Event"
        assert event_data["category"] == "Music"
        assert event_data["time"] == "14:30"
        assert event_data["date"] == "2025-09-12"
        assert event_data["venue"] == "Test Venue"
        assert event_data["url"] == "https://example.com/test"

    def test_get_events_for_itinerary_success(self, sample_events):
        """Test successful event retrieval for itinerary."""

        provider = MockEventsProvider(sample_events)
        service = EventsService(provider)
        
        mock_query = Mock()
        mock_query.city = "Kyiv"
        mock_query.start_date = datetime(2025, 9, 10)
        mock_query.end_date = datetime(2025, 9, 15)
        mock_query.categories = ["music", "food"]

        result = service.get_events_for_itinerary(mock_query)

        assert result is not None
        assert isinstance(result, dict)
        assert len(provider.fetch_calls) == 1
        assert provider.fetch_calls[0]['city'] == "Kyiv"

    def test_get_events_for_itinerary_no_query(self):
        """Test handling of None event query."""
        service = EventsService(MockEventsProvider())

        result = service.get_events_for_itinerary(None)

        assert result is None

    def test_get_events_for_itinerary_missing_dates(self):
        """Test handling of missing start or end dates."""
 
        service = EventsService(MockEventsProvider())
        
        # Mock EventQuery with missing dates
        mock_query = Mock()
        mock_query.city = "Kyiv"
        mock_query.start_date = None
        mock_query.end_date = datetime(2025, 9, 15)
        mock_query.categories = ["music"]

        result = service.get_events_for_itinerary(mock_query)

        assert result is None

    def test_get_events_for_itinerary_empty_dates(self):
        """Test handling of empty string dates."""
        # Arrange
        service = EventsService(MockEventsProvider())
        
        # Mock EventQuery with empty dates
        mock_query = Mock()
        mock_query.city = "Kyiv"
        mock_query.start_date = ""
        mock_query.end_date = ""
        mock_query.categories = ["music"]

        result = service.get_events_for_itinerary(mock_query)

        assert result is None

    def test_get_events_for_itinerary_validation_error(self):
        """Test handling of validation errors from get_events."""
        provider = MockEventsProvider()
        provider.fetch = Mock(side_effect=ValueError("Invalid date range"))
        service = EventsService(provider)
        
        mock_query = Mock()
        mock_query.city = "Kyiv"
        mock_query.start_date = datetime(2025, 9, 10)
        mock_query.end_date = datetime(2025, 9, 15)
        mock_query.categories = ["music"]

        result = service.get_events_for_itinerary(mock_query)

        assert result is None

    def test_get_events_for_itinerary_type_error(self):
        """Test handling of type errors from get_events."""

        provider = MockEventsProvider()
        provider.fetch = Mock(side_effect=TypeError("Invalid type"))
        service = EventsService(provider)
        
        mock_query = Mock()
        mock_query.city = "Kyiv"
        mock_query.start_date = datetime(2025, 9, 10)
        mock_query.end_date = datetime(2025, 9, 15)
        mock_query.categories = ["music"]

        result = service.get_events_for_itinerary(mock_query)

        assert result is None

    def test_get_events_for_itinerary_unexpected_error(self):
        """Test handling of unexpected errors from get_events."""

        provider = MockEventsProvider()
        provider.fetch = Mock(side_effect=Exception("Unexpected error"))
        service = EventsService(provider)
        
        mock_query = Mock()
        mock_query.city = "Kyiv"
        mock_query.start_date = datetime(2025, 9, 10)
        mock_query.end_date = datetime(2025, 9, 15)
        mock_query.categories = ["music"]


        result = service.get_events_for_itinerary(mock_query)


        assert result is None

    def test_get_events_for_itinerary_datetime_conversion(self):
        """Test conversion of datetime to date for start_date."""

        events = [
            Event(
                title="Test Event",
                category="Music",
                date=datetime(2025, 9, 12, 14, 0),
                venue="Test Venue",
                url="https://example.com/test"
            )
        ]
        provider = MockEventsProvider(events)
        service = EventsService(provider)
        
        mock_query = Mock()
        mock_query.city = "Kyiv"
        mock_query.start_date = datetime(2025, 9, 10)  # datetime object
        mock_query.end_date = datetime(2025, 9, 15)
        mock_query.categories = ["music"]

        result = service.get_events_for_itinerary(mock_query)

        assert result is not None
        assert "Day 3" in result  # 2025-09-12 is 3 days after 2025-09-10
        assert "afternoon" in result["Day 3"]


class TestEventsToolIntegration:
    """Test cases for events tool integration."""

    @pytest.fixture
    def mock_tavily_config(self):
        """Mock Tavily configuration settings."""
        mock_config = Mock()
        mock_config.tavily_api_key = "test_api_key"
        mock_config.tavily_api_url = "https://api.tavily.com/search"
        mock_config.tavily_include_answer = "advanced"
        mock_config.tavily_country = "ukraine"
        mock_config.tavily_max_results = 5
        mock_config.tavily_timeout = 30
        return mock_config

    @pytest.fixture
    def mock_settings(self, mock_tavily_config):
        """Mock settings object with Tavily configuration."""
        mock_settings = Mock()
        mock_settings.tavily = mock_tavily_config
        return mock_settings

    @pytest.fixture
    def sample_events(self):
        """Sample events for tool testing."""
        return [
            Event(
                title="Kyiv Music Festival",
                category="Music",
                date=datetime(2025, 9, 12, 18, 0),
                venue="Maidan Nezalezhnosti",
                url="https://example.com/event1"
            ),
            Event(
                title="Food & Wine Expo",
                category="Food",
                date=datetime(2025, 9, 13, 12, 0),
                venue="Expo Center",
                url="https://example.com/event2"
            )
        ]

    @patch('app.agents.tools.TavilyEventsProvider')
    def test_get_events_tool_success(self, mock_provider_class, mock_settings, sample_events):
        """Test successful event retrieval through the get_events tool."""
        # Arrange
        mock_provider = Mock(spec=TavilyEventsProvider)
        mock_provider_class.return_value = mock_provider
        
        # Mock EventsService to return our sample events
        with patch('app.agents.tools.EventsService') as mock_service_class:
            mock_service = Mock()
            mock_service.get_events.return_value = sample_events
            mock_service_class.return_value = mock_service
            
            # Act - Call the tool function directly (not as a LangChain tool)
            result = get_events.func("Kyiv", "2025-09-10", "2025-09-15", ["Music", "Food"])
            
            # Assert
            assert result is not None
            result_data = json.loads(result)
            assert len(result_data) == 2
            assert result_data[0]["name"] == "Kyiv Music Festival"
            assert result_data[1]["name"] == "Food & Wine Expo"
            
            # Verify service was called with correct parameters
            mock_service.get_events.assert_called_once_with(
                "Kyiv", 
                "2025-09-10", 
                "2025-09-15", 
                ["Music", "Food"]
            )

    @patch('app.agents.tools.TavilyEventsProvider')
    def test_get_events_tool_default_end_date(self, mock_provider_class, mock_settings, sample_events):
        """Test that get_events tool defaults end_date to start_date when not provided."""
        # Arrange
        mock_provider = Mock(spec=TavilyEventsProvider)
        mock_provider_class.return_value = mock_provider
        
        with patch('app.agents.tools.EventsService') as mock_service_class:
            mock_service = Mock()
            mock_service.get_events.return_value = sample_events
            mock_service_class.return_value = mock_service
            
            # Act
            result = get_events.func("Kyiv", "2025-09-10", None, ["Music"])
            
            # Assert
            mock_service.get_events.assert_called_once_with(
                "Kyiv", 
                "2025-09-10", 
                "2025-09-10",  # Should default to start_date
                ["Music"]
            )

    @patch('app.agents.tools.TavilyEventsProvider')
    def test_get_events_tool_no_categories(self, mock_provider_class, mock_settings, sample_events):
        """Test get_events tool with no categories specified."""
        # Arrange
        mock_provider = Mock(spec=TavilyEventsProvider)
        mock_provider_class.return_value = mock_provider
        
        with patch('app.agents.tools.EventsService') as mock_service_class:
            mock_service = Mock()
            mock_service.get_events.return_value = sample_events
            mock_service_class.return_value = mock_service
            
            # Act
            result = get_events.func("Kyiv", "2025-09-10", "2025-09-15", None)
            
            # Assert
            mock_service.get_events.assert_called_once_with(
                "Kyiv", 
                "2025-09-10", 
                "2025-09-15", 
                None
            )

    @patch('app.agents.tools.TavilyEventsProvider')
    def test_get_events_tool_service_exception(self, mock_provider_class, mock_settings):
        """Test get_events tool handles service exceptions gracefully."""
        # Arrange
        mock_provider = Mock(spec=TavilyEventsProvider)
        mock_provider_class.return_value = mock_provider
        
        with patch('app.agents.tools.EventsService') as mock_service_class:
            mock_service = Mock()
            mock_service.get_events.side_effect = Exception("Service error")
            mock_service_class.return_value = mock_service
            
            # Act
            result = get_events.func("Kyiv", "2025-09-10", "2025-09-15", ["Music"])
            
            # Assert
            result_data = json.loads(result)
            assert "error" in result_data
            assert "Failed to get events: Service error" in result_data["error"]
            assert result_data["city"] == "Kyiv"
            assert result_data["start_date"] == "2025-09-10"

    @patch('app.agents.tools.TavilyEventsProvider')
    def test_get_events_tool_provider_initialization_error(self, mock_provider_class, mock_settings):
        """Test get_events tool handles provider initialization errors."""
        # Arrange
        mock_provider_class.side_effect = Exception("Provider initialization failed")
        
        # Act
        result = get_events.func("Kyiv", "2025-09-10", "2025-09-15", ["Music"])
        
        # Assert
        result_data = json.loads(result)
        assert "error" in result_data
        assert "Failed to get events: Provider initialization failed" in result_data["error"]

    @patch('app.agents.tools.TavilyEventsProvider')
    def test_get_events_tool_json_serialization(self, mock_provider_class, mock_settings, sample_events):
        """Test that get_events tool properly serializes Event objects to JSON."""
        # Arrange
        mock_provider = Mock(spec=TavilyEventsProvider)
        mock_provider_class.return_value = mock_provider
        
        with patch('app.agents.tools.EventsService') as mock_service_class:
            mock_service = Mock()
            mock_service.get_events.return_value = sample_events
            mock_service_class.return_value = mock_service
            
            # Act
            result = get_events.func("Kyiv", "2025-09-10", "2025-09-15", ["Music"])
            
            # Assert
            result_data = json.loads(result)
            assert isinstance(result_data, list)
            assert len(result_data) == 2
            
            # Verify event structure
            event1 = result_data[0]
            assert "name" in event1
            assert "category" in event1
            assert "date" in event1
            assert "venue" in event1
            assert "url" in event1
            assert event1["name"] == "Kyiv Music Festival"
            assert event1["category"] == "Music"

    def test_get_events_tool_with_real_provider_mock(self, mock_settings, sample_events):
        """Test get_events tool with mocked TavilyEventsProvider but real EventsService flow."""
        # Arrange
        project_root = "/test/project/root"
        
        with patch('app.services.events.providers.tavily.ConfigLoader') as mock_loader_class:
            mock_loader = Mock()
            mock_loader.get_settings.return_value = mock_settings
            mock_loader_class.return_value = mock_loader
            
            # Mock the actual TavilyEventsProvider.fetch method
            with patch.object(TavilyEventsProvider, 'fetch', return_value=sample_events) as mock_fetch:
                # Act
                result = get_events.func("Kyiv", "2025-09-10", "2025-09-15", ["Music"])
                
                # Assert
                result_data = json.loads(result)
                assert len(result_data) == 2
                assert result_data[0]["name"] == "Kyiv Music Festival"
                
                # Verify provider was initialized with correct project_root
                mock_loader_class.assert_called_once()
                
                # Verify fetch was called with correct parameters
                mock_fetch.assert_called_once_with(
                    "Kyiv",
                    datetime(2025, 9, 10),
                    datetime(2025, 9, 15),
                    ["Music"]
                )
