import pytest
from unittest.mock import Mock, patch
from app.services.itinerary.itinerary import (
    PlacesLocation,
    GetPlacesItem,
    ItineraryService,
)


class TestPlacesLocation:
    """Test PlacesLocation serialization"""

    def test_valid_location(self):
        loc = PlacesLocation(lng=50.123, lat=30.456)
        assert loc.lng == 50.123
        assert loc.lat == 30.456


class TestGetPlacesItem:
    """Test GetPlacesItem serialization and validation"""

    def test_serialize_minimal(self):
        item = GetPlacesItem(
            rating=4.5,
            name="Test Place",
            place_id="abc123",
            formatted_address="123 Test St",
            types=["restaurant"],
            location=PlacesLocation(lng=50.0, lat=30.0),
        )
        data = item.serialize()

        assert data["name"] == "Test Place"
        assert data["place_id"] == "abc123"
        assert data["rating"] == 4.5
        assert data["formatted_address"] == "123 Test St"
        assert data["types"] == ["restaurant"]
        assert data["location"] == {"lat": 30.0, "lng": 50.0}
        assert data["description"] is None
        assert data["wiki_title"] is None
        assert data["wiki_url"] is None

    def test_serialize_with_wiki_data(self):
        item = GetPlacesItem(
            rating=4.8,
            name="Famous Museum",
            place_id="xyz789",
            formatted_address="456 Culture Ave",
            types=["museum"],
            location=PlacesLocation(lng=51.0, lat=31.0),
            description="A famous museum",
            wiki_title="Famous Museum",
            wiki_url="https://en.wikipedia.org/wiki/Famous_Museum",
        )
        data = item.serialize()

        assert data["description"] == "A famous museum"
        assert data["wiki_title"] == "Famous Museum"
        assert data["wiki_url"] == "https://en.wikipedia.org/wiki/Famous_Museum"

    def test_extract_location_from_geometry(self):
        """Test location extraction from Google Places geometry format"""
        raw_data = {
            "rating": 4.0,
            "name": "Test",
            "place_id": "id123",
            "formatted_address": "Address",
            "types": ["point_of_interest"],
            "geometry": {"location": {"lat": 25.5, "lng": 55.5}},
        }
        item = GetPlacesItem(**raw_data)
        assert item.location.lat == 25.5
        assert item.location.lng == 55.5

    def test_extra_fields_ignored(self):
        """Test that extra fields from API response are ignored"""
        raw_data = {
            "rating": 4.0,
            "name": "Test",
            "place_id": "id123",
            "formatted_address": "Address",
            "types": ["point_of_interest"],
            "location": PlacesLocation(lat=25.5, lng=55.5),
            "unknown_field": "should be ignored",
            "another_extra": 123,
        }
        item = GetPlacesItem(**raw_data)
        assert item.name == "Test"


class TestItineraryServiceContract:
    """Contract-based tests for ItineraryService"""

    @pytest.fixture
    def mock_config(self):
        """Mock configuration with API key"""
        mock_settings = Mock()
        mock_settings.itinerary.api_key = "test_api_key"
        
        with patch("app.services.itinerary.itinerary.ConfigLoader") as mock_loader:
            mock_loader.return_value.get_settings.return_value = mock_settings
            yield mock_loader

    @pytest.fixture
    def service(self, mock_config):
        """Create service instance with mocked config"""
        with patch("app.services.itinerary.itinerary.googlemaps.Client"):
            return ItineraryService(project_root="/fake/root")

    def test_initialization_requires_api_key(self):
        """Test service fails without API key"""
        mock_settings = Mock()
        mock_settings.itinerary.api_key = None
        
        with patch("app.services.itinerary.itinerary.ConfigLoader") as mock_loader:
            mock_loader.return_value.get_settings.return_value = mock_settings
            
            with pytest.raises(RuntimeError, match="MAP_API_KEY is required"):
                ItineraryService(project_root="/fake/root")

    def test_initialization_requires_itinerary_config(self):
        """Test service fails without itinerary settings"""
        mock_settings = Mock()
        mock_settings.itinerary = None
        
        with patch("app.services.itinerary.itinerary.ConfigLoader") as mock_loader:
            mock_loader.return_value.get_settings.return_value = mock_settings
            
            with pytest.raises(RuntimeError, match="Itinerary settings are missing"):
                ItineraryService(project_root="/fake/root")

    def test_get_places_returns_list_of_items(self, service):
        """Test get_places returns correctly typed list"""
        mock_response = {
            "results": [
                {
                    "name": "Place 1",
                    "place_id": "id1",
                    "rating": 4.5,
                    "formatted_address": "Address 1",
                    "types": ["restaurant"],
                    "geometry": {"location": {"lat": 30.0, "lng": 50.0}},
                }
            ]
        }
        service.client.places = Mock(return_value=mock_response)

        with patch.object(service, "_best_wiki_for_place", return_value=None):
            results = service.get_places("restaurants", "New York", k=5)

        assert isinstance(results, list)
        assert len(results) == 1
        assert isinstance(results[0], GetPlacesItem)
        assert results[0].name == "Place 1"

    def test_get_places_limits_results_to_k(self, service):
        """Test get_places respects k parameter"""
        mock_response = {
            "results": [
                {
                    "name": f"Place {i}",
                    "place_id": f"id{i}",
                    "rating": 4.0,
                    "formatted_address": f"Address {i}",
                    "types": ["restaurant"],
                    "geometry": {"location": {"lat": 30.0 + i, "lng": 50.0}},
                }
                for i in range(10)
            ]
        }
        service.client.places = Mock(return_value=mock_response)

        with patch.object(service, "_best_wiki_for_place", return_value=None):
            results = service.get_places("restaurants", "London", k=3)

        assert len(results) == 3

    def test_get_places_handles_api_error(self, service):
        """Test get_places raises RuntimeError on API failure"""
        from googlemaps import exceptions as gmaps_exceptions
        
        service.client.places = Mock(
            side_effect=gmaps_exceptions.ApiError("API_ERROR")
        )

        with pytest.raises(RuntimeError, match="Google Places API error"):
            service.get_places("museums", "Paris", k=5)

    def test_get_places_enriches_with_wikimedia(self, service):
        """Test get_places enriches results with Wikimedia data"""
        mock_response = {
            "results": [
                {
                    "name": "Eiffel Tower",
                    "place_id": "id1",
                    "rating": 4.9,
                    "formatted_address": "Paris, France",
                    "types": ["point_of_interest"],
                    "geometry": {"location": {"lat": 48.8584, "lng": 2.2945}},
                }
            ]
        }
        service.client.places = Mock(return_value=mock_response)

        wiki_data = {
            "title": "Eiffel Tower",
            "extract": "Famous iron lattice tower in Paris",
            "fullurl": "https://en.wikipedia.org/wiki/Eiffel_Tower",
        }
        with patch.object(service, "_best_wiki_for_place", return_value=wiki_data):
            results = service.get_places("Eiffel Tower", "Paris", k=1)

        assert results[0].wiki_title == "Eiffel Tower"
        assert results[0].description == "Famous iron lattice tower in Paris"
        assert results[0].wiki_url == "https://en.wikipedia.org/wiki/Eiffel_Tower"

    def test_get_places_gracefully_handles_wikimedia_failure(self, service):
        """Test get_places continues when Wikimedia enrichment fails"""
        mock_response = {
            "results": [
                {
                    "name": "Place 1",
                    "place_id": "id1",
                    "rating": 4.5,
                    "formatted_address": "Address",
                    "types": ["restaurant"],
                    "geometry": {"location": {"lat": 30.0, "lng": 50.0}},
                }
            ]
        }
        service.client.places = Mock(return_value=mock_response)

        with patch.object(service, "_best_wiki_for_place", side_effect=Exception("Wiki error")):
            results = service.get_places("restaurants", "City", k=1)

        # Should still return results without wiki data
        assert len(results) == 1
        assert results[0].description is None
        assert results[0].wiki_title is None