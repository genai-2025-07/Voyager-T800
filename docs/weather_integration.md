## Weather Context Provider (OpenWeather)

This feature fetches a short-range forecast from OpenWeather, normalizes it to simple labels (sunny, rainy, cold, hot, etc.) in Celsius, and injects it into the itinerary prompt so recommendations adapt to the weather. A Streamlit toggle controls whether weather is used.

### Setup
- Set your API key via environment: `OPENWEATHER_API_KEY=...`
- Optional overrides:
  - `OPENWEATHER_BASE_URL` (default `https://api.openweathermap.org`)
- Configuration lives in `app/config/default.yaml` under `weather:`.

### Code Overview
- `app/services/weather.py` — Async `WeatherService` that:
  - Geocodes city → lat/lon
  - Calls 5-day/3-hourly forecast
  - Aggregates to daily buckets with min/max temp, precipitation, wind
  - Normalizes to labels and returns a compact JSON
  - Caches results with TTL; includes retries and timeouts
- `app/utils/date_utils.py` — Extracts a best-effort date range and a simple city heuristic from user text.
- `app/chains/itinerary_chain.py` — Builds `weather_context` and passes it to the prompt when enabled.
- `app/prompts/test_itinerary_prompt.txt` — Updated to include optional weather context and guidance on how to adapt.
- `app/frontend/chat_interface.py` — Adds a checkbox "Enable weather-aware recommendations" and shows a simple summary card.

### UI Behavior
- Toggle in sidebar controls weather usage. When enabled and a city/date range can be inferred, a summary card displays the next few days' labels and temps.
- The frontend remains a thin client; the toggle is surfaced to the chain via `VOYAGER_USE_WEATHER` env var.

### Tests
- `tests/test_weather_service.py` — Mocks API calls to validate normalization, Celsius handling, and disabled fallback.
- `tests/test_chain_weather_integration.py` — Verifies toggle behavior and context formatting without network calls.

### Examples
- Kyiv: "Plan a 2‑day trip to Kyiv from 2025-09-20 to 2025-09-21"
- Lviv: "Trip to Lviv 2025-10-05 to 2025-10-07 with museums"

When rainy, itineraries should emphasize museums and cafes; when sunny, parks and walking tours.
