## Team Decision on Metadata Source

As of the August 6th meeting, after discussing information below the team agreed to use **Google Maps API** as the primary tool for gathering metadata for places listed in the attractions dataset.

This includes:
- Using **Google Places API** and related services to retrieve detailed metadata such as:
  - Opening hours
  - Address and contact info
  - Ratings (if available)
- Enriching attraction data with **contextual nearby places** such as:
  - Cafés
  - Parks
  - Restaurants
  - Other POIs within walking distance

The reasoning behind choosing Google Maps first:
- Reliable and rich place detail coverage.
- Consistent formatting across different types of locations.
- Relatively generous **free tier** for the current needs.

If the free quota proves insufficient, or if interactive mapping needs evolve, we will consider **Mapbox** as an alternative or complementary solution, especially for rendering and interactivity. **Specific criteria for switching to Mapbox**: If we consistently exceed 9,000 requests/month (90% of Google's free tier) or require interactive features unavailable in Google Maps (such as custom map styling, offline capabilities, or advanced 3D rendering).


## API Research Summary

- **Mapbox**, **Here Maps**, and **Google Maps** each offer SDKs/APIs for maps, routing, geocoding, etc., with various free-tier quotas (monthly requests or active users).
- **OpenStreetMap** is entirely free/open data; you host or use community servers for tiles and POI.
- **OpenRouteService** (built on OSM data) offers geocoding, routing, isochrones, matrix, etc., with a public free tier.
- **Leaflet** is an open-source JavaScript library for interactive maps, with no built-in service quotas.

***

## 1. Mapbox

| API/SDK                   | Description                                                                       | Free Tier (Monthly)        |
|---------------------------|-----------------------------------------------------------------------------------|-----------------------------|
| **Navigation SDK**        | In-app turn-by-turn routing and guidance                                          | 1 000 trips                 |
| **Directions API**        | Driving/walking/cycling routes with traffic                                      | 100 000 requests            |
| **Optimization API**      | Multi-stop routing, optimized stop order                                          | 100 000 requests            |
| **Matrix API**            | Travel-time/distance matrices, reachability                                       | 100 000 requests            |
| **Isochrone API**         | Area contours reachable within a time budget                                      | 100 000 requests            |
| **Maps SDKs for Mobile**  | Dynamic map renderers for Android & iOS                                           | 25 000 MAU*                 |
| **Static Images API**     | Generate styled map snapshots                                                     | 50 000 requests             |
| **Vector Tiles API**      | Retrieve vector-tile data                                                         | 200 000 requests            |
| **Search (Geocoding)**    | Address & POI lookup by name or coords                                            | 100 000 requests            |
| **Search (POI Category)** | List POIs by category (e.g. “coffee shops” around coords)                         | 50 000 requests             |
| **Temporary Geocoding**   | Geocoding/place search without persistent indexing                                | 100 000 requests            |

\*MAU = Monthly Active Users

**Note**: Some APIs may require billing enabled for higher quotas. After the free tier, pricing is typically per-request with volume discounts available.

***

## 2. Here Maps

| API/SDK                         | Description                                                                            | Free Tier (Monthly)    |
|---------------------------------|----------------------------------------------------------------------------------------|------------------------|
| **Vector Tile**                 | Pre-rendered tiles & client-side vector rendering                                       | 30 000 requests        |
| **Geocode / Reverse Geocode**   | Address ↔ geographic coordinate lookup                                                 | 30 000 requests        |
| **Discover / Search**           | Category & keyword search for places                                                    | 5 000 requests         |
| **Matrix Routing**              | Time/distance matrices between origins & destinations                                   | 2 500 requests         |
| **Routing (Car/Bike/Walk)**     | Directions for multiple modes                                                          | 30 000 requests        |

**Note**: All quotas are per API key/project. Multiple API keys can be created for different use cases.

***

## 3. Google Maps Platform

| API                              | Description                                         | Free Tier (Monthly) |
| -------------------------------- | --------------------------------------------------- | ------------------- |
| **Maps JavaScript API**          | Interactive, styled maps                            | 10 000 loads        |
| **Maps Embed API**               | Simple `<iframe>` maps & Street View                | Unlimited           |
| **Routes: Compute Route Matrix** | Travel-time/distance matrix                         | 10 000 elements     |
| **Routes: Compute Routes**       | Real-time directions (traffic, transit, bike, walk) | 10 000 requests     |
| **Geocoding API**                | Forward & reverse geocoding                         | 10 000 requests     |
| **Geolocation API**              | Device location via cell/WiFi data                  | 10 000 requests     |
| **Places API — Place Details**   | Detailed info (addresses, opening hours, etc.)      | 10 000 requests     |
|                                  |                                                     |                     |

**Note**: A credit card is required to activate the free tier, even for limited use. Billing is automatically enabled but charges only apply after exceeding free quotas.

***

## 4. OpenStreetMap

- **Data Licensing**: CC BY-SA; free to use, redistribute, and modify with attribution.
- **Tile Hosting**:
    - **osm.org tiles**: Public tile server for small usage; heavy use requires self-hosting (e.g., TileServer GL).
    - **Third-Party Hosts**: Services like Thunderforest, OpenMapTiles (often with their own free tiers).
- **APIs**:
    - **Overpass API**: Query raw OSM data (nodes, ways, relations).
        - ~10,000 requests/day, ~1GB download/day (guidelines); multiple slots per user with queue system.
    - **Nominatim**: Geocoding/search engine.
        - **Maximum 1 request per second**; Bulk geocoding is discouraged; for production or high-volume use, consider self-hosting Nominatim..
        - Self-host for production/unlimited.
- **POI / Nearby Search**:
    - Use Overpass to find amenities (e.g., `amenity=cafe`) within a radius of coordinates.
    - **Example Overpass query** for finding cafés within 500m of coordinates:
      ```
      [out:json][timeout:25];
      (
        node["amenity"="cafe"](around:500,50.4501,30.5234);
        way["amenity"="cafe"](around:500,50.4501,30.5234);
        relation["amenity"="cafe"](around:500,50.4501,30.5234);
      );
      out body;
      >;
      out skel qt;
      ```

***

## 5. OpenRouteService

Built on OSM data—offers routing, isochrones, matrix, geocoding, etc., under free API keys:

| Service        | Free Tier (Monthly) |
| -------------- | ------------------- |
| **Directions** | 10000 requests      |
| **Matrix**     | 2 500 calls         |
| **Isochrones** | 2 500 calls         |
| **Geocoding**  | 5 000 requests      |
| **Pois**       | 2500 requests       |

**Note**: Registration required for API keys. Free tier intended for non-commercial use; commercial applications may require paid plans. Rate limiting applies to prevent abuse.

***

## 6. Leaflet

- **What it is**: Leaflet is an MIT-licensed JavaScript library for interactive maps. It does not provide map data or APIs; it’s primarily for rendering and user interaction.