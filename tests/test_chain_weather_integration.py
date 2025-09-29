"""
Tests for weather integration with the itinerary chain.

This test suite verifies that weather context is properly integrated
into the LLM chain and respects user preferences.
"""

from unittest.mock import patch

import pytest

from app.chains import itinerary_chain as chain_module


class TestWeatherChainIntegration:
    """Test weather integration with the itinerary chain."""

    def test_build_weather_context_respects_toggle(self, monkeypatch):
        """Test that weather toggle disables weather context generation."""
        # Arrange: Disable weather toggle
        monkeypatch.setenv("VOYAGER_USE_WEATHER", "0")

        # Act: Generate weather context
        payload = {"user_input": "Plan trip to Kyiv from 2025-09-20 to 2025-09-21"}
        result = chain_module._build_weather_context(payload)

        # Assert: Weather should be disabled
        assert result == ""

    def test_build_weather_context_happy_path(self, monkeypatch):
        """Test successful weather context generation."""
        # Arrange: Enable weather toggle
        monkeypatch.setenv("VOYAGER_USE_WEATHER", "1")

        # Mock weather service to avoid network calls
        def mock_weather_service(project_root, city, start_date, end_date):
            return {
                "city": city,
                "units": "metric",
                "days": [
                    {
                        "date": "2025-09-20",
                        "label": "rainy",
                        "temp_min_c": 12.0,
                        "temp_max_c": 16.0,
                        "precipitation_mm": 3.0,
                        "wind_mps": 4.0,
                        "description": "light rain",
                    }
                ],
            }

        # Act: Generate weather context with mocked service
        with patch.object(chain_module, "get_weather_forecast_sync", new=mock_weather_service):
            payload = {"user_input": "Trip to Lviv 2025-09-20 to 2025-09-21"}
            result = chain_module._build_weather_context(payload)

        # Assert: Weather context should be properly formatted
        assert "<weather>" in result and "</weather>" in result
        assert "city=Lviv" in result
        assert "2025-09-20" in result
        assert "label=rainy" in result
        assert "tmin=12.0C" in result
        assert "tmax=16.0C" in result

    def test_build_weather_context_no_city(self, monkeypatch):
        """Test weather context generation when no city is found."""
        # Arrange: Enable weather toggle
        monkeypatch.setenv("VOYAGER_USE_WEATHER", "1")

        # Act: Generate weather context without city
        payload = {"user_input": "I want to travel somewhere"}
        result = chain_module._build_weather_context(payload)

        # Assert: Should return empty string when no city found
        assert result == ""

    def test_build_weather_context_weather_service_error(self, monkeypatch):
        """Test weather context generation when weather service fails."""
        # Arrange: Enable weather toggle
        monkeypatch.setenv("VOYAGER_USE_WEATHER", "1")

        # Mock weather service to return error
        def mock_weather_service_error(project_root, city, start_date, end_date):
            return {"error": "api_failed"}

        # Act: Generate weather context with failing service
        with patch.object(chain_module, "get_weather_forecast_sync", new=mock_weather_service_error):
            payload = {"user_input": "Trip to Lviv 2025-09-20 to 2025-09-21"}
            result = chain_module._build_weather_context(payload)

        # Assert: Should return empty string when service fails
        assert result == ""

    def test_build_weather_context_multiple_days(self, monkeypatch):
        """Test weather context generation for multi-day trips."""
        # Arrange: Enable weather toggle
        monkeypatch.setenv("VOYAGER_USE_WEATHER", "1")

        # Mock weather service with multiple days
        def mock_weather_service_multi_day(project_root, city, start_date, end_date):
            return {
                "city": city,
                "units": "metric",
                "days": [
                    {
                        "date": "2025-09-20",
                        "label": "sunny",
                        "temp_min_c": 18.0,
                        "temp_max_c": 25.0,
                        "precipitation_mm": 0.0,
                        "wind_mps": 3.0,
                        "description": "clear sky",
                    },
                    {
                        "date": "2025-09-21",
                        "label": "cloudy",
                        "temp_min_c": 15.0,
                        "temp_max_c": 22.0,
                        "precipitation_mm": 1.5,
                        "wind_mps": 4.5,
                        "description": "broken clouds",
                    }
                ],
            }

        # Act: Generate weather context for multi-day trip
        with patch.object(chain_module, "get_weather_forecast_sync", new=mock_weather_service_multi_day):
            payload = {"user_input": "2 days in Kyiv from 2025-09-20 to 2025-09-21"}
            result = chain_module._build_weather_context(payload)

        # Assert: Should include both days
        assert "<weather>" in result and "</weather>" in result
        assert "city=Kyiv" in result
        assert "2025-09-20" in result
        assert "2025-09-21" in result
        assert "label=sunny" in result
        assert "label=cloudy" in result

    def test_build_weather_context_empty_user_input(self, monkeypatch):
        """Test weather context generation with empty user input."""
        # Arrange: Enable weather toggle
        monkeypatch.setenv("VOYAGER_USE_WEATHER", "1")

        # Act: Generate weather context with empty input
        payload = {"user_input": ""}
        result = chain_module._build_weather_context(payload)

        # Assert: Should return empty string
        assert result == ""

    def test_build_weather_context_invalid_user_input(self, monkeypatch):
        """Test weather context generation with invalid user input."""
        # Arrange: Enable weather toggle
        monkeypatch.setenv("VOYAGER_USE_WEATHER", "1")

        # Act: Generate weather context with invalid input
        payload = {"user_input": None}
        result = chain_module._build_weather_context(payload)

        # Assert: Should return empty string
        assert result == ""


if __name__ == "__main__":
    pytest.main([__file__])