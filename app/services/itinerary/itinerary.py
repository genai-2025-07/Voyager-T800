import requests
from functools import lru_cache
from typing import Optional, Any, Dict, List

import googlemaps
from googlemaps import exceptions as gmaps_exceptions

from pydantic import BaseModel, model_validator
from app.config.loader import ConfigLoader
import logging

logger = logging.getLogger(__name__)


class PlacesLocation(BaseModel):
    lng: float
    lat: float


class GetPlacesItem(BaseModel):
    rating: float
    name: str
    place_id: str
    formatted_address: str
    types: List[str]
    location: PlacesLocation

    # optional Wikimedia fields
    description: Optional[str] = None
    wiki_title: Optional[str] = None
    wiki_url: Optional[str] = None

    @model_validator(mode="before")
    def extract_location(cls, values: dict) -> Any:
        if "location" not in values:
            geom = values.get("geometry")
            if isinstance(geom, dict):
                loc = geom.get("location")
                if loc is not None:
                    new = dict(values)
                    new["location"] = PlacesLocation(**loc)
                    return new
        return values

    def serialize(self) -> Dict[str, Any]:
        place_data: Dict[str, Any] = {
            "name": self.name,
            "place_id": self.place_id,
            "formatted_address": self.formatted_address,
            "rating": self.rating,
            "types": list(self.types),
            "location": {"lat": self.location.lat, "lng": self.location.lng},
        }

        place_data["description"] = self.description
        place_data["wiki_title"] = self.wiki_title
        place_data["wiki_url"] = self.wiki_url

        return place_data

    class Config:
        extra = "ignore"


class ItineraryService:
    def __init__(self, project_root: str, timeout: int = 6,
                 geo_radius: int = 1000, geo_limit: int = 10) -> None:
        self.timeout = timeout
        self.geo_radius = geo_radius
        self.geo_limit = geo_limit

        loader = ConfigLoader(project_root=project_root)
        settings = loader.get_settings()
        if not settings.itinerary:
            raise RuntimeError("Itinerary settings are missing in configuration.")
        it = settings.itinerary
        if not it.api_key:
            raise RuntimeError("MAP_API_KEY is required for itinerary features.")

        self.client = googlemaps.Client(key=it.api_key)

    def _wikimedia_api(self, lang: str, params: dict) -> dict:
        """Low-level call to Wikimedia API. Raises requests.RequestException or ValueError on failure."""
        base = f"https://{lang}.wikipedia.org/w/api.php"
        params = dict(params)
        params.setdefault("format", "json")
        headers = {"User-Agent": "ItineraryService/1.0"}
        r = requests.get(base, params=params, headers=headers, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def _wikimedia_geosearch(self, lang: str, lat: float, lon: float) -> List[dict]:
        params = {
            "action": "query",
            "list": "geosearch",
            "gscoord": f"{lat}|{lon}",
            "gsradius": self.geo_radius,
            "gslimit": self.geo_limit,
        }
        try:
            data = self._wikimedia_api(lang, params)
            return data.get("query", {}).get("geosearch", [])
        except (requests.RequestException, ValueError) as e:
            logger.debug("Wikimedia geosearch failed (non-fatal): %s", e)
            return []

    def _wikimedia_textsearch(self, lang: str, title: str, city: Optional[str] = None, limit: int = 5) -> List[dict]:
        q = title if not city else f"{title} {city}"
        params = {"action": "query", "list": "search", "srsearch": q, "srlimit": limit}
        try:
            data = self._wikimedia_api(lang, params)
            return data.get("query", {}).get("search", [])
        except (requests.RequestException, ValueError) as e:
            logger.debug("Wikimedia text search failed (non-fatal) for '%s': %s", q, e)
            return []

    def _wikimedia_get_extracts_and_url(self, lang: str, pageids: List[int]) -> dict:
        if not pageids:
            return {}
        ids_str = "|".join(map(str, pageids))
        params = {
            "action": "query",
            "pageids": ids_str,
            "prop": "extracts|info",
            "exintro": 1,
            "explaintext": 1,
            "inprop": "url",
        }
        try:
            data = self._wikimedia_api(lang, params)
            return data.get("query", {}).get("pages", {})
        except (requests.RequestException, ValueError) as e:
            logger.debug("Wikimedia extracts lookup failed (non-fatal): %s", e)
            return {}

    def _pick_best_from_geosearch(self, geolist: List[dict]) -> Optional[dict]:
        if not geolist:
            return None
        return min(geolist, key=lambda x: x.get("dist", float("inf")))

    def _best_wiki_for_place(self, lat: float, lng: float, name: str, lang: str = "en") -> Optional[dict]:
        """Best-effort: returns dict with title/extract/fullurl or None."""
        try:
            geo_hits = self._wikimedia_geosearch(lang, lat, lng)
            if not geo_hits:
                return None

            exact = next((h for h in geo_hits if h.get("title", "").lower() == name.lower()), None)
            chosen = exact or geo_hits[0]
            pageid = chosen.get("pageid")
            if not pageid:
                return None

            pages = self._wikimedia_get_extracts_and_url(lang, [pageid])
            page = pages.get(str(pageid))
            if page and (page.get("extract") or page.get("fullurl")):
                return {"title": page.get("title"), "extract": (page.get("extract") or "").strip(), "fullurl": page.get("fullurl")}
            return None
        except Exception as e:
            logger.debug("Wikimedia enrichment failed for '%s' (%s): %s", name, f"{lat},{lng}", e)
            return None
    
    def _enrich_with_wikimedia(
        self,
        items: List[GetPlacesItem],
        language: str,
        query: str
    ) -> int:
        """
        Best-effort enrichment of `items` using Wikimedia.
        Returns the number of items successfully enriched.
        Non-fatal: exceptions are logged and enrichment continues.
        """
        enriched_count = 0
        for it in items:
            try:
                wiki = self._best_wiki_for_place(
                    it.location.lat, it.location.lng, name=query, lang=language
                )
                if wiki:
                    it.description = wiki.get("extract")
                    it.wiki_title = wiki.get("title")
                    it.wiki_url = wiki.get("fullurl")
                    enriched_count += 1
            except Exception:
                logger.exception("Exception occurred during Wikimedia enrichment for item: %s", getattr(it, "name", "<unknown>"))
        return enriched_count

    def get_places(
        self,
        query: str,
        city: str,
        k: int,
        language: str = "en"
    ) -> List[GetPlacesItem]:
        """
        Retrieve places from Google Places and perform best-effort Wikimedia enrichment.
        Google API failures are treated as fatal; Wikimedia enrichment is best-effort.
        """
        places_query = f"{query} {city}"
        try:
            resp = self.client.places(places_query, language=language)
            places = resp.get("results", [])
        except gmaps_exceptions.ApiError as e:
            raise RuntimeError(f"Google Places API error for query '{places_query}': {e}") from e
        except Exception as e:
            raise RuntimeError(f"Failed to call Google Places API for query '{places_query}': {e}") from e

        items = [GetPlacesItem(**p) for p in places[:k]]

        enriched_count = self._enrich_with_wikimedia(items, language, query)

        logger.info("Found %d places for query '%s' and enriched %d/%d with Wikimedia", len(items), places_query, enriched_count, len(items))

        return items
