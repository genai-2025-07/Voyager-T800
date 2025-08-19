# Weaviate  Database Schema Documentation

## Overview

This document describes the vector database schema, indexing strategies, and design decisions for a tourism attraction management system built on Weaviate. 

## Schema Design

### Primary Class: `Attraction`

The main class that stores all place-related data with unified schema for attractions, restaurants, cafes, etc.

#### Properties

| Property                         |           Type | Storage / Example (Weaviate-style)                                | Tokenization / Notes                            |
| -------------------------------- | -------------: | ----------------------------------------------------------------- | ----------------------------------------------- |
| `name`                           |           text | `"Café Example"`                                                  | `word` — searchable place name                  |
| `description`                    |           text | long text                                                         | `word` — full-text description                  |
| `chunk_id`                       |           text | `"page_001_chunk_03"`                                             | -                                               |
| `address`                        |           text | `"123 Main St, Kyiv, Ukraine"`                                    | - (human-readable formatted\_address)           |
| `postal_code`                    |           text | `"01001"`                                                         | - (from address\_components)                    |
| `administrative_area_level_1`    |           text | `"Kyiv"`                                                          | A first-order civil entity below the country level. Within the United States, these administrative levels are states.-                                               |
| `administrative_area_level_2`    |           text | `"Kyiv City"`                                                     | A second-order civil entity below the country level. Within the United States, these administrative levels are counties. Not all nations exhibit these administrative levels.                                               |
| `sublocality_level_1`            |           text | `"Podil"`                                                         | A first-order civil entity below a locality.                                                |
| `coordinates`                    | geoCoordinates | `{ "latitude": 50.4501, "longitude": 30.5234 }`                   | geo — for geo queries (in future)                           |
| `place_id`                       |           text | `"ChIJ…"`                                                         | unique external id                              |
| `phone_number`                   |           text | `"+380-44-123-4567"`                                              | international\_phone\_number                    |
| `maps_url`                       |           text | `"https://maps.google.com/..."`                                   | link to google maps place page -                                               |
| `opening_hours`                  |         object | see detailed structure below                                      | structured weekly object (see below)            |
| `price_level`                    |            int | `2`                                                               | numeric from Google Places (0..4)               |
| `rating`                         |         number | `4.6`                                                             | float (0.0–5.0)                                 |
| `reviews`                        |      object\[] | see `reviews` structure below                                     | array of review objects (not just text)         |
| `tags`                           |        text\[] | `["establishment", "food", "park", "point_of_interest", "store"]` | from `types`                                    |
| `wheelchair_accessible_entrance` |        boolean | `true`                                                            | from place details                              |
| `serves_beer`                    |        boolean | `true`                                                            |                                                 |
| `serves_breakfast`               |        boolean | `false`                                                           |                                                 |
| `serves_brunch`                  |        boolean | `true`                                                            |                                                 |
| `serves_dinner`                  |        boolean | `true`                                                            |                                                 |
| `serves_lunch`                   |        boolean | `true`                                                            |                                                 |
| `serves_vegetarian_food`         |        boolean | `true`                                                            |                                                 |
| `serves_wine`                    |        boolean | `true`                                                            |                                                 |
| `takeout`                        |        boolean | `true`                                                            |                                                 |
| `last_updated`                   |       dateTime | `"2025-08-20T22:05:00+03:00"`                                     | when the DB record was last updated             |

## opening_hours object structure
```json
"opening_hours": {
  "type": "weekly",
  "week_start": "2025-08-14",
  "week_end": "2025-08-20",
  "last_refreshed": "2025-08-20T21:00:00+03:00",
  "weekly": {
    "Monday":    [ {"start":"12:00","end":"21:00"} ],
    "Tuesday":   [ {"start":"12:00","end":"21:00"} ],
    "Wednesday": [ {"start":"12:00","end":"21:00"} ],
    "Thursday":  [ {"start":"12:00","end":"21:00"} ],
    "Friday":    [ {"start":"12:00","end":"21:00"} ],
    "Saturday":  [ {"start":"10:00","end":"21:00"} ],
    "Sunday":    [ {"start":"10:00","end":"21:00"} ]
  }
}
```
## reviews object structure: 
 - english only reviews (language: "eng"), only 5 reviews for each place 
```json
"reviews": [
  {
    "author_name": "Olena",
    "rating": 5,
    "text": "Fantastic pastries!",
    "time": "2025-06-10T14:20:00+03:00",
    "language": "eng",
  }
  .....
]
```

## Initial Validation Constraints


| Field / Object                   | Required? | Type / Format / Range                                | Notes / Limits |
|----------------------------------|:---------:|------------------------------------------------------|----------------|
| `name`                           | Yes       | `text` — non-empty, max length **200**               | Trim whitespace; reject empty strings. |
| `description`                    | Yes        | `text` — max length **5000**                         | Allow rich text but limit size. |
| `chunk_id`                       | Yes       | `text` — pattern `^[a-zA-Z0-9_\-]+$`, max **100**    | Unique per document chunk. |
| `address`                        | No        | `text` — max length **300**                          | — |
| `postal_code`                    | No        | `text` — max length **12**   | — |
| `administrative_area_level_*`    | No        | `text` — max length **100**                          | — |
| `sublocality_level_1`            | No        | `text` — max length **100**                          | — |
| `coordinates`                    | Yes| `geoCoordinates` — `{latitude: -90..90, longitude: -180..180}` | Both values numeric; reject null/invalid ranges. |
| `place_id`                       | Yes        | `text` — max length **128**                          | Id provied by maps API |
| `phone_number`                   | No        | `text` — E.164 recommended (pattern `^\+\d{7,15}$`)  | Normalize to E.164 on ingest. |
| `maps_url`                       | Yes        | `text` — valid URL (scheme http/https), max **1000** | - |
| `opening_hours` (object)         | No        | `type` ∈ {`weekly`}, `week_start`/`week_end` ISO dates; time strings `HH:MM` | Ensure `week_start` ≤ `week_end`; per-day intervals non-overlapping and `start` < `end`. |
| `price_level`                    | No        | `int` ∈ [0,4]                                        | - |
| `rating`                         | No        | `number` ∈ [0.0, 5.0], precision ≤ 2 decimal places  | - |
| `reviews` (array)                | No        | Array length ≤ **5**; each `{author_name,text,time,rating,language}` | `rating` ∈ [1,5] integer; `time` ISO8601; `language` ISO-639-2 (e.g., `eng`). |
| `tags`                           | No        | `text[]` — max items **20**, each max length **50**  | - |
| Boolean fields (`takeout`, `serves_*`, `wheelchair_accessible_entrance`) | No | `boolean` | Default `false` or `null` depending on ingestion policy. |
| `last_updated`                   | Yes       | `dateTime` — ISO8601 (UTC or timezone-aware)         | Set at write/update; used for TTL/refresh logic. |


## Indexing Strategy

#### Dynamic Index Type

The system uses Weaviate's **dynamic vector indexing** which provides optimal performance across different data scales:

- **Initial Phase (< 10,000 objects)**: Flat index for exact search
- **Scaling Phase (> 10,000 objects)**: Automatic transition to HNSW

#### Distance Metric: Cosine Similarity

**Choice Rationale**:
- Best suited for normalized embedding vectors
- Scale-invariant, focusing on direction rather than magnitude
- Industry standard for semantic similarity
- Compatible with most embedding models (OpenAI, Sentence Transformers, etc.)

### Inverted Index Configuration

Full-text search optimization with:
- **Index timestamps**: Enabled for temporal queries
- **Index null state**: Track missing values
- **Index property length**: Optimize for length-based queries

### Tokenization Strategy

| Field Type | Tokenization | Use Case |
|------------|--------------|----------|
| Name/Description | `word` | Full-text search with stemming |
| Category | `field` | Exact match filtering |
| Tags | `word` | Flexible tag search |

## Search Capabilities

### 1. Vector Search
- Pure semantic similarity search
- Supports filtering by metadata
- Returns distance/similarity scores

### 2. Keyword Search (BM25)
- Traditional text search
- Configurable search fields
- Best for exact term matching

### 3. Hybrid Search
- Combines vector and keyword search
- Alpha parameter (0-1) for weighting
- Fusion strategies: RANKED or RELATIVE_SCORE
## Scalability Considerations

### Data Volume Thresholds

| Volume | Index Type | Performance Characteristics |
|--------|------------|---------------------------|
| 0-10K | Flat | Exact search, highest quality |
| 10K-100K | HNSW | Good balance of speed/quality |
| 100K-1M | HNSW | Optimized for large scale |
| 1M+ | HNSW + Sharding | Distributed architecture |

# Extensibility

**Will the schema adapt smoothly?**  
Yes — if you keep extensions additive, use explicit classes, references, and simple versioning.

## Quick recommendations
- **New classes:** add `Event`, `TransportNode`, etc., instead of overloading `Attraction`.  
- **References:** link classes (`Attraction` ↔ `Event`) for explicit, queryable relationships.  
- **Shared metadata:** duplicate common fields or extract a small `Location` class if you prefer normalization.  
- **Optional fields & tags:** keep properties optional so existing objects stay valid.

## Operational caveats
- Adding fields is non-destructive (old objects show `null`).  
- Changing embedding/vectorizer requires re-embedding (re-indexing).  
- Renames/removals are breaking — plan migrations and keep a `schema_version`.  
- Monitor inverted-index size and performance as large text fields accumulate.
