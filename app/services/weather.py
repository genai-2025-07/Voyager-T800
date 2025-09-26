import asyncio
import json
import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import aiohttp

from app.config.loader import ConfigLoader


logger = logging.getLogger(__name__)


@dataclass
class NormalizedForecast:
    """Lightweight, normalized daily forecast representation in Celsius.

    This data model keeps only the fields that are useful for itinerary planning
    and for concise UI display. Temperatures are expected in Celsius.
    """

    date: str
    label: str  # e.g., "sunny", "rainy", "cloudy", "snowy", "cold", "hot"
    temp_min_c: float
    temp_max_c: float
    precipitation_mm: float
    wind_mps: float
    description: str


class _TTLCache:
    """Simple in-memory TTL cache for storing forecasts per (city, start, end).

    Note:
        - This is process-local and ephemeral. It's sufficient for a single-process
          Streamlit/CLI run. For multi-process deployments, a shared cache should be used.
    """

    def __init__(self, ttl_seconds: int) -> None:
        self._ttl = max(0, int(ttl_seconds))
        self._store: Dict[str, Tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def _key(self, city: str, start: str, end: str) -> str:
        return json.dumps([city.strip().lower(), start, end])

    def get(self, city: str, start: str, end: str, ttl_override_seconds: Optional[int] = None) -> Optional[Any]:
        if self._ttl == 0 and (ttl_override_seconds is None or int(ttl_override_seconds) == 0):
            return None
        key = self._key(city, start, end)
        
        with self._lock:
            entry = self._store.get(key)
            if not entry:
                return None
            ts, value = entry
            effective_ttl = self._ttl if ttl_override_seconds is None else max(0, int(ttl_override_seconds))
            if effective_ttl == 0:
                return None
            if time.time() - ts > effective_ttl:
                self._store.pop(key, None)
                return None
            return value

    def set(self, city: str, start: str, end: str, value: Any) -> None:
        if self._ttl == 0:
            return
        key = self._key(city, start, end)
        
        with self._lock:
            self._store[key] = (time.time(), value)


# Process-wide cache instance (initialized on first WeatherService creation)
_GLOBAL_CACHE: Optional[_TTLCache] = None


def _coerce_date(d: Any) -> datetime:
    if isinstance(d, datetime):
        return d
    if isinstance(d, (int, float)):
        return datetime.fromtimestamp(d)
    if isinstance(d, str):
        # Accept common formats; fallback to ISO
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y"):
            try:
                return datetime.strptime(d, fmt)
            except ValueError:
                pass
        return datetime.fromisoformat(d)
    raise ValueError(f"Unsupported date value: {d}")


def _normalize_label(weather_main: str, temp_min: float, temp_max: float, precipitation_mm: float) -> str:
    weather = (weather_main or "").strip().lower()

    if "snow" in weather:
        return "snowy"
    if "rain" in weather or "drizzle" in weather or precipitation_mm >= 2.0:
        return "rainy"
    if "cloud" in weather:
        return "cloudy"
    if temp_max <= 0.0:
        return "freezing"
    if temp_max < 10.0:
        return "cold"
    if temp_min > 25.0:
        return "hot"
    return "sunny"


def _aggregate_to_daily(list_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Aggregate OpenWeather 3-hourly forecast to per-day buckets.

    We compute min/max temps, sum precipitation, and choose the most frequent
    weather "main"/description for the day.
    """
    buckets: Dict[str, Dict[str, Any]] = {}
    for item in list_items:
        dt_txt = item.get("dt_txt")  # e.g., "2025-09-20 12:00:00"
        if not dt_txt:
            # Fallback to unix timestamp
            dt = datetime.fromtimestamp(int(item.get("dt", 0)))
        else:
            dt = datetime.strptime(dt_txt, "%Y-%m-%d %H:%M:%S")
        day_key = dt.strftime("%Y-%m-%d")

        main = item.get("main", {})
        temp_min = float(main.get("temp_min", main.get("temp", 0.0)))
        temp_max = float(main.get("temp_max", main.get("temp", 0.0)))

        weather_arr = item.get("weather", []) or [{}]
        # Process all weather objects for more accurate aggregation
        for w in weather_arr:
            if w:  # Skip empty weather objects
                weather_main = w.get("main", "")
                description = w.get("description", "")
                # Count each weather condition and description
                bucket["weather_counts"][weather_main] = bucket["weather_counts"].get(weather_main, 0) + 1
                bucket["desc_counts"][description] = bucket["desc_counts"].get(description, 0) + 1

        rain_mm = 0.0
        snow_mm = 0.0
        # API uses metrics like {"3h": 0.21}
        if isinstance(item.get("rain"), dict):
            rain_mm = float(item["rain"].get("3h", 0.0))
        if isinstance(item.get("snow"), dict):
            snow_mm = float(item["snow"].get("3h", 0.0))
        precipitation = rain_mm + snow_mm

        wind_mps = float(item.get("wind", {}).get("speed", 0.0))

        bucket = buckets.setdefault(day_key, {
            "temp_min": temp_min,
            "temp_max": temp_max,
            "precip": 0.0,
            "wind": 0.0,
            "weather_counts": {},
            "desc_counts": {},
        })
        bucket["temp_min"] = min(bucket["temp_min"], temp_min)
        bucket["temp_max"] = max(bucket["temp_max"], temp_max)
        bucket["precip"] += precipitation
        bucket["wind"] = max(bucket["wind"], wind_mps)

    daily: List[Dict[str, Any]] = []
    for day, b in sorted(buckets.items()):
        top_weather = max(b["weather_counts"].items(), key=lambda kv: kv[1])[0] if b["weather_counts"] else ""
        top_desc = max(b["desc_counts"].items(), key=lambda kv: kv[1])[0] if b["desc_counts"] else ""
        daily.append({
            "date": day,
            "temp_min": round(b["temp_min"], 1),
            "temp_max": round(b["temp_max"], 1),
            "precip": round(b["precip"], 1),
            "wind": round(b["wind"], 1),
            "weather_main": top_weather,
            "description": top_desc,
        })
    return daily


class WeatherService:
    """OpenWeather-based forecast provider with normalization and caching.

    Usage:
        service = WeatherService(project_root)
        data = await service.get_weather_forecast("Lviv", "2025-09-20", "2025-09-23")
    """

    def __init__(self, project_root: str) -> None:
        loader = ConfigLoader(project_root=project_root)
        settings = loader.get_settings()
        if not settings.weather:
            raise RuntimeError("Weather settings are missing in configuration.")
        w = settings.weather
        if not w.api_key:
            raise RuntimeError("OPENWEATHER_API_KEY is required for weather features.")

        self._api_key = w.api_key
        self._base_url = w.base_url.rstrip("/")
        self._units = w.units
        self._timeout = w.request_timeout_seconds
        self._retry_attempts = w.retry_attempts
        self._retry_min = w.retry_backoff_min
        self._retry_max = w.retry_backoff_max
        global _GLOBAL_CACHE
        if _GLOBAL_CACHE is None:
            _GLOBAL_CACHE = _TTLCache(w.cache_ttl_seconds)
        self._cache = _GLOBAL_CACHE

    async def _get_city_coordinates(self, session: aiohttp.ClientSession, city: str) -> Optional[Tuple[float, float]]:
        params = {"q": city, "appid": self._api_key, "limit": 1}
        url = f"{self._base_url}/geo/1.0/direct"
        async with session.get(url, params=params, timeout=self._timeout) as resp:
            if resp.status != 200:
                text = await resp.text()
                logger.warning(f"Geocoding failed for '{city}': {resp.status} {text}")
                return None
            data = await resp.json()
            if not data:
                return None
            entry = data[0]
            return float(entry.get("lat", 0.0)), float(entry.get("lon", 0.0))

    async def _fetch_forecast_raw(self, session: aiohttp.ClientSession, lat: float, lon: float) -> Dict[str, Any]:
        params = {
            "lat": lat,
            "lon": lon,
            "appid": self._api_key,
            "units": self._units,
        }
        url = f"{self._base_url}/data/2.5/forecast"
        async with session.get(url, params=params, timeout=self._timeout) as resp:
            if resp.status != 200:
                text = await resp.text()
                logger.error(f"Error {resp.status} from weather API: {text}")
                raise RuntimeError(f"OpenWeather forecast error: {resp.status} {text}")
            return await resp.json()

    def _slice_by_dates(self, daily: List[Dict[str, Any]], start: datetime, end: datetime) -> List[Dict[str, Any]]:
        res: List[Dict[str, Any]] = []
        cur = start.date()
        last = end.date()
        want: set[str] = set()
        while cur <= last:
            want.add(cur.strftime("%Y-%m-%d"))
            cur = cur + timedelta(days=1)
        for d in daily:
            if d.get("date") in want:
                res.append(d)
        return res

    def _to_normalized(self, city: str, days: List[Dict[str, Any]]) -> Dict[str, Any]:
        normalized: List[NormalizedForecast] = []
        for d in days:
            label = _normalize_label(d.get("weather_main", ""), d.get("temp_min", 0.0), d.get("temp_max", 0.0), d.get("precip", 0.0))
            normalized.append(
                NormalizedForecast(
                    date=d["date"],
                    label=label,
                    temp_min_c=float(d["temp_min"]),
                    temp_max_c=float(d["temp_max"]),
                    precipitation_mm=float(d["precip"]),
                    wind_mps=float(d["wind"]),
                    description=(d.get("description") or "").strip(),
                )
            )
        summary_labels = [n.label for n in normalized]
        return {
            "city": city,
            "units": "metric",
            "days": [n.__dict__ for n in normalized],
            "summary": {
                "labels": summary_labels,
            },
        }

    async def get_weather_forecast(
        self,
        city: str,
        start_date: Any,
        end_date: Any,
        *,
        force_refresh: bool = False,
        ttl_override_seconds: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Fetch and normalize weather forecast for the given city and date range.

        Args:
            city: City name (e.g., "Kyiv", "Lviv").
            start_date: Inclusive start date (str, datetime, or epoch).
            end_date: Inclusive end date (str, datetime, or epoch).
            force_refresh: If True, bypass the cache and fetch fresh data.
            ttl_override_seconds: Optional TTL (seconds) to use for this call's
                cache lookup decision. Does not mutate the global cache's TTL;
                only affects whether an existing entry is considered fresh.

        Returns:
            Normalized JSON dict with daily forecasts in Celsius. On failure, returns
            an empty payload with a `disabled` or `error` note so the caller can
            gracefully fall back.
        """
        
        try:
            start_dt = _coerce_date(start_date)
            end_dt = _coerce_date(end_date)
        except Exception as e:
            return {"error": "invalid_dates"}

        cache_hit = None if force_refresh else self._cache.get(
            city,
            start_dt.strftime("%Y-%m-%d"),
            end_dt.strftime("%Y-%m-%d"),
            ttl_override_seconds=ttl_override_seconds,
        )
        if cache_hit is not None and not force_refresh:
            return cache_hit

        attempt = 0
        backoff = self._retry_min
        async with aiohttp.ClientSession() as session:
            while True:
                try:
                    coords = await self._get_city_coordinates(session, city)
                    if not coords:
                        return {"error": "geocoding_failed"}
                    lat, lon = coords
                    raw = await self._fetch_forecast_raw(session, lat, lon)
                    daily = _aggregate_to_daily(raw.get("list", []))
                    sliced = self._slice_by_dates(daily, start_dt, end_dt)
                    normalized = self._to_normalized(city, sliced)
                    self._cache.set(
                        city,
                        start_dt.strftime("%Y-%m-%d"),
                        end_dt.strftime("%Y-%m-%d"),
                        normalized,
                    )
                    return normalized
                except Exception as e:
                    attempt += 1
                    if attempt > self._retry_attempts:
                        logger.warning(f"Weather request failed after retries: {e}")
                        return {"error": "request_failed"}
                    await asyncio.sleep(min(self._retry_max, max(self._retry_min, backoff)))
                    backoff = min(self._retry_max, backoff * 2)


def get_weather_forecast_sync(
    project_root: str,
    city: str,
    start_date: Any,
    end_date: Any,
    *,
    force_refresh: bool = False,
    ttl_override_seconds: Optional[int] = None,
) -> Dict[str, Any]:
    """Synchronous convenience wrapper for environments without asyncio plumbing."""
    service = WeatherService(project_root=project_root)
    
    # Check if we're already in an event loop
    try:
        loop = asyncio.get_running_loop()
        # We're in an event loop, use create_task
        task = loop.create_task(
            service.get_weather_forecast(
                city,
                start_date,
                end_date,
                force_refresh=force_refresh,
                ttl_override_seconds=ttl_override_seconds,
            )
        )
        # Wait for the task to complete
        return loop.run_until_complete(task)
    except RuntimeError:
        # No event loop running, safe to use asyncio.run
        return asyncio.run(
            service.get_weather_forecast(
                city,
                start_date,
                end_date,
                force_refresh=force_refresh,
                ttl_override_seconds=ttl_override_seconds,
            )
        )


