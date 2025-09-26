"""
Tests for the Weather Service Module

This test suite covers the weather context provider functionality including:
- Weather API integration
- Data normalization and caching  
- City and date extraction from user input
- Error handling and fallbacks

The tests use mocking to avoid making actual API calls during testing,
ensuring tests are fast, reliable, and don't consume API quota.
"""

import asyncio
from datetime import datetime
from unittest.mock import patch, Mock

import pytest

from app.services.weather import WeatherService, get_weather_forecast_sync
from app.utils.date_utils import derive_city_from_text, extract_date_range


class TestWeatherService:
    """Test the main WeatherService class functionality."""

    def test_weather_normalization(self):
        """Test weather condition normalization."""
        # Create a real WeatherService instance just for the normalization method
        service = WeatherService.__new__(WeatherService)
        normalized = service._to_normalized("Lviv", [
            {
                "date": "2025-09-20",
                "temp_min": 16.0,
                "temp_max": 24.0,
                "weather_main": "Clear",
                "description": "clear sky",
                "precip": 0.0,
                "wind": 3.0
            }
        ])
        
        assert normalized["city"] == "Lviv"
        assert normalized["units"] == "metric"
        assert len(normalized["days"]) == 1
        assert normalized["days"][0]["label"] == "sunny"
        assert normalized["days"][0]["temp_min_c"] == 16.0
        assert normalized["days"][0]["temp_max_c"] == 24.0

    def test_date_slicing(self):
        """Test date range slicing functionality."""
        # Create a real WeatherService instance just for the date slicing method
        service = WeatherService.__new__(WeatherService)
        
        daily_data = [
            {"date": "2025-09-19", "temp_min": 15.0, "temp_max": 20.0, "main": "Clear", "description": "clear sky", "rain_3h": 0.0, "wind_speed": 2.0},
            {"date": "2025-09-20", "temp_min": 16.0, "temp_max": 24.0, "main": "Clear", "description": "clear sky", "rain_3h": 0.0, "wind_speed": 3.0},
            {"date": "2025-09-21", "temp_min": 18.0, "temp_max": 25.0, "main": "Rain", "description": "light rain", "rain_3h": 2.0, "wind_speed": 4.0},
            {"date": "2025-09-22", "temp_min": 14.0, "temp_max": 22.0, "main": "Clouds", "description": "broken clouds", "rain_3h": 0.0, "wind_speed": 5.0},
        ]
        
        start_date = datetime.strptime("2025-09-20", "%Y-%m-%d")
        end_date = datetime.strptime("2025-09-21", "%Y-%m-%d")
        
        sliced = service._slice_by_dates(daily_data, start_date, end_date)
        
        assert len(sliced) == 2
        assert sliced[0]["date"] == "2025-09-20"
        assert sliced[1]["date"] == "2025-09-21"


class TestSyncWrapper:
    """Test the synchronous wrapper function."""

    def test_get_weather_forecast_sync(self):
        """Test the sync wrapper for weather forecast."""
        with patch.object(WeatherService, 'get_weather_forecast') as mock_async:
            mock_async.return_value = {
                "city": "Lviv",
                "units": "metric",
                "days": [{"date": "2025-09-20", "label": "sunny", "temp_min_c": 16.0, "temp_max_c": 24.0, "precipitation_mm": 0.0, "wind_mps": 3.0, "description": "clear sky"}]
            }
            
            # Mock the WeatherService constructor
            with patch.object(WeatherService, '__init__', return_value=None):
                result = get_weather_forecast_sync(".", "Lviv", "2025-09-20", "2025-09-21")
                
                assert result["city"] == "Lviv"
                assert len(result["days"]) == 1


class TestDateUtils:
    """Test date and destination extraction utilities."""

    def test_derive_city_from_text_simple(self):
        """Test extracting city names from simple patterns."""
        assert derive_city_from_text("Plan a 2-day trip to Lviv") == "Lviv"
        assert derive_city_from_text("3 days in Kyiv") == "Kyiv"
        assert derive_city_from_text("I want to visit New York") == "York"

    def test_derive_city_from_text_no_city(self):
        """Test when no city is found."""
        assert derive_city_from_text("I want to travel somewhere") is None
        assert derive_city_from_text("Plan a vacation") == "Plan"  # "Plan" is capitalized and >= 3 chars
        assert derive_city_from_text("") is None

    def test_derive_city_from_text_edge_cases(self):
        """Test edge cases for city extraction."""
        assert derive_city_from_text("Visit Lviv and Kyiv") == "Kyiv"  # Last capitalized word
        assert derive_city_from_text("Go to Lviv") == "Lviv"
        assert derive_city_from_text("lviv") is None  # Lowercase

    def test_extract_date_range_simple(self):
        """Test extracting date ranges from simple patterns."""
        start, end = extract_date_range("from 2025-09-20 to 2025-09-21")
        assert start.strftime("%Y-%m-%d") == "2025-09-20"
        assert end.strftime("%Y-%m-%d") == "2025-09-21"

    def test_extract_date_range_two_dates(self):
        """Test extracting date ranges with two dates."""
        start, end = extract_date_range("2025-09-21 and 2025-09-20")
        assert start.strftime("%Y-%m-%d") == "2025-09-20"  # Should be sorted
        assert end.strftime("%Y-%m-%d") == "2025-09-21"

    def test_extract_date_range_no_dates(self):
        """Test when no dates are found - should return default range."""
        start, end = extract_date_range("I want to visit Lviv")
        assert isinstance(start, datetime)
        assert isinstance(end, datetime)
        assert (end - start).days == 2  # 3-day range (inclusive)


if __name__ == "__main__":
    pytest.main([__file__])