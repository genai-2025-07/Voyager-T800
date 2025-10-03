import requests
from functools import lru_cache
from typing import Optional, Any

import googlemaps

from pydantic import BaseModel, model_validator
from app.config.loader import ConfigLoader

class PlacesLocation(BaseModel):
    lng: float
    lat: float


class GetPlacesItem(BaseModel):
    rating: float
    name: str
    place_id: str
    formatted_address: str
    types: list[str]
    location: PlacesLocation

    # added optional fields that will be filled from Wikimedia
    description: Optional[str] = None
    wiki_title: Optional[str] = None
    wiki_url: Optional[str] = None

    @model_validator(mode="before")
    def extract_location(cls, values: dict) -> Any:
        # values is the raw input mapping (or something mapping-like)
        if "location" not in values:
            geom = values.get("geometry")
            if isinstance(geom, dict):
                loc = geom.get("location")
                if loc is not None:
                    # copy to avoid mutating whatever was passed in
                    new = dict(values)
                    new["location"] = PlacesLocation(**loc)
                    return new
        return values

    class Config:
        extra = 'ignore' 


class ItineraryService:
    def __init__(self, project_root: str) -> None:
        loader = ConfigLoader(project_root=project_root)
        settings = loader.get_settings()
        if not settings.itinerary:
            raise RuntimeError("Weather settings are missing in configuration.")
        it = settings.itinerary
        if not it.api_key:
            raise RuntimeError("MAP_API_KEY is required for weather features.")

        self.client = googlemaps.Client(key=it.api_key)

    @lru_cache(maxsize=256)
    def _wikimedia_api(self, lang: str, params: dict) -> dict:
        base = f"https://{lang}.wikipedia.org/w/api.php"
        params = dict(params)
        params.setdefault("format", "json")
        headers = {
            'User-Agent': 'ItineraryService/1.0 (https://example.com/contact)'
        }
        r = requests.get(base, params=params, headers=headers, timeout=6)
        r.raise_for_status()
        return r.json()

    def _wikimedia_geosearch(self, lang: str, lat: float, lon: float, radius: int = 1000, limit: int = 10) -> list[dict]:
        params = {
            "action": "query",
            "list": "geosearch",
            "gscoord": f"{lat}|{lon}",
            "gsradius": radius,
            "gslimit": limit
        }
        data = self._wikimedia_api(lang, tuple(sorted(params.items())))
        return data.get("query", {}).get("geosearch", [])

    def _wikimedia_textsearch(self, lang: str, title: str, city: Optional[str] = None, limit: int = 5) -> list[dict]:
        q = title if not city else f"{title} {city}"
        params = {
            "action": "query",
            "list": "search",
            "srsearch": q,
            "srlimit": limit
        }
        data = self._wikimedia_api(lang, tuple(sorted(params.items())))
        return data.get("query", {}).get("search", [])

    def _wikimedia_get_extracts_and_url(self, lang: str, pageids: list[int]) -> dict:
        if not pageids:
            return {}
        ids_str = "|".join(map(str, pageids))
        params = {
            "action": "query",
            "pageids": ids_str,
            "prop": "extracts|info",
            "exintro": 1,
            "explaintext": 1,
            "inprop": "url"
        }
        data = self._wikimedia_api(lang, tuple(sorted(params.items())))
        return data.get("query", {}).get("pages", {})

    def _pick_best_from_geosearch(self, geolist: list[dict]) -> Optional[dict]:
        # Prefer nearest (geosearch returns 'dist' when available)
        if not geolist:
            return None
        geolist_sorted = sorted(geolist, key=lambda x: x.get("dist", float("inf")))
        return geolist_sorted[0]

    def _best_wiki_for_place(self, lat: float, lng: float, name: str, lang="en") -> dict:
        # text_hits = self._wikimedia_textsearch(lang, name, city)
        text_hits = self._wikimedia_geosearch(lang, lat, lng)
        if text_hits:
            exact = next((h for h in text_hits if h.get("title", "").lower() == name.lower()), None)
            chosen = text_hits[0] or exact
            pageid = chosen.get("pageid")
            pages = self._wikimedia_get_extracts_and_url(lang, [pageid])
            page = pages.get(str(pageid))
            if page and (page.get("extract") or page.get("fullurl")):
                return {
                    "title": page.get("title"),
                    "extract": (page.get("extract") or "").strip(),
                    "fullurl": page.get("fullurl")
                }
        
    def get_places(self, query: str, city: str, k: int, language="en") -> list[GetPlacesItem]:
        '''
         query: str,
        '''
        places_query = query + " " + city
        places = self.client.places(places_query, language=language)["results"]
        items = [GetPlacesItem(**places[i]) for i in range(min(k, len(places)))]

        # enrich with Wikimedia info (best-effort). Keep this non-fatal.
        for it in items:
            try:
                wiki = self._best_wiki_for_place(it.location.lat, it.location.lng, name=query, lang=language)
                if wiki:
                    it.description = wiki.get("extract")
                    it.wiki_title = wiki.get("title")
                    it.wiki_url = wiki.get("fullurl")
            except Exception:
                # keep going even if one lookup fails
                continue

        return items
