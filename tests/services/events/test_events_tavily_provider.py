"""
Unit tests for TavilyEventsProvider.

Tests the Tavily API integration, mocking external dependencies
to ensure fast, deterministic tests.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import requests
from app.services.events.providers.tavily import TavilyEventsProvider
from app.services.events.models import Event


class TestTavilyEventsProvider:
    """Test cases for TavilyEventsProvider."""

    @pytest.fixture
    def provider(self):
        """Create a TavilyEventsProvider instance for testing."""
        with patch.dict('os.environ', {'TAVILY_API_KEY': 'test_api_key'}):
            return TavilyEventsProvider()

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
        """Mock Tavily API response."""
        import json
        return {
            "answer": f"""
            Here are some events in Kyiv:
            ```json
            {json.dumps(sample_events_data)}
            ```
            """
        }

    def test_provider_initialization(self, provider):
        """Test that provider initializes with correct API key and URL."""
        assert provider.api_key == "test_api_key"
        assert provider.api_url == "https://api.tavily.com/search"

    def test_provider_initialization_missing_api_key(self):
        """Test that provider raises error when API key is missing."""
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(ValueError, match="TAVILY_API_KEY environment variable is not set"):
                TavilyEventsProvider()

    @patch('requests.post')
    def test_fetch_events_success(self, mock_post, provider, mock_tavily_response, sample_events_data):
        """Test successful event fetching from Tavily API."""
        # Arrange
        mock_response = Mock()
        mock_response.json.return_value = mock_tavily_response
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        city = "Kyiv"
        start_date = datetime(2025, 9, 10)
        end_date = datetime(2025, 9, 15)
        categories = ["music", "food"]

        # Act
        events = provider.fetch(city, start_date, end_date, categories)

        # Assert
        assert len(events) == 2
        assert all(isinstance(event, Event) for event in events)
        assert events[0].title == "Kyiv Music Festival"
        assert events[0].category == "Music"
        assert events[1].title == "Food & Wine Expo"
        assert events[1].category == "Food"

        # Verify API call was made correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[1]["headers"]["Authorization"] == "Bearer test_api_key"
        assert "query" in call_args[1]["json"]
        assert call_args[1]["json"]["country"] == "ukraine"
        assert call_args[1]["json"]["max_results"] == 5
        assert call_args[1]["json"]["include_answer"] == "advanced"

    @patch('requests.post')
    def test_fetch_events_api_error(self, mock_post, provider):
        """Test handling of API errors."""
        # Arrange
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("API Error")
        mock_post.return_value = mock_response

        city = "Kyiv"
        start_date = datetime(2025, 9, 10)
        end_date = datetime(2025, 9, 15)

        # Act & Assert
        with pytest.raises(requests.RequestException, match="Tavily API HTTP error"):
            provider.fetch(city, start_date, end_date)

    @patch('requests.post')
    def test_fetch_events_invalid_json_response(self, mock_post, provider):
        """Test handling of invalid JSON in API response."""
        # Arrange
        mock_response = Mock()
        mock_response.json.return_value = {"answer": "No valid JSON here"}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        city = "Kyiv"
        start_date = datetime(2025, 9, 10)
        end_date = datetime(2025, 9, 15)

        # Act
        events = provider.fetch(city, start_date, end_date)

        # Assert
        assert events == []

    @patch('requests.post')
    def test_fetch_events_empty_response(self, mock_post, provider):
        """Test handling of empty API response."""
        # Arrange
        mock_response = Mock()
        mock_response.json.return_value = {"answer": ""}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        city = "Kyiv"
        start_date = datetime(2025, 9, 10)
        end_date = datetime(2025, 9, 15)

        # Act
        events = provider.fetch(city, start_date, end_date)

        # Assert
        assert events == []

    @patch('requests.post')
    def test_fetch_events_network_error(self, mock_post, provider):
        """Test handling of network errors."""
        # Arrange
        mock_post.side_effect = requests.ConnectionError("Network error")

        city = "Kyiv"
        start_date = datetime(2025, 9, 10)
        end_date = datetime(2025, 9, 15)

        # Act & Assert
        with pytest.raises(requests.RequestException, match="Failed to connect to Tavily API"):
            provider.fetch(city, start_date, end_date)

    @patch('requests.post')
    def test_fetch_events_with_none_categories(self, mock_post, provider, mock_tavily_response, sample_events_data):
        """Test fetching events when categories is None."""
        # Arrange
        mock_response = Mock()
        mock_response.json.return_value = mock_tavily_response
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        city = "Kyiv"
        start_date = datetime(2025, 9, 10)
        end_date = datetime(2025, 9, 15)

        # Act
        events = provider.fetch(city, start_date, end_date, categories=None)

        # Assert
        assert len(events) == 2
        mock_post.assert_called_once()

    @patch('requests.post')
    def test_fetch_events_with_empty_categories(self, mock_post, provider, mock_tavily_response, sample_events_data):
        """Test fetching events when categories is empty list."""
        # Arrange
        mock_response = Mock()
        mock_response.json.return_value = mock_tavily_response
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        city = "Kyiv"
        start_date = datetime(2025, 9, 10)
        end_date = datetime(2025, 9, 15)

        # Act
        events = provider.fetch(city, start_date, end_date, categories=[])

        # Assert
        assert len(events) == 2
        mock_post.assert_called_once()

    def test_fetch_events_invalid_event_data(self, provider):
        """Test handling of invalid event data that can't be converted to Event model."""
        # This test would require mocking the extract_events function to return invalid data
        # and ensuring the provider handles it gracefully
        pass
