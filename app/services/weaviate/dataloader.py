from pathlib import Path
import json
import ast
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import pandas as pd
from pydantic import ValidationError

from app.services.weaviate.data_models.attraction_models import (
    EmbeddingModel,
    EmbeddingMetadataModel,
    CoordinatesModel,
    OpeningHoursModel,
    ReviewModel,
    AttractionModel,
    ChunkData,
    AttractionWithChunks
)

from app.config.logger.logger import setup_logger

from dotenv import load_dotenv

# load environment from same folder as this file (app/services/weaviate/.env)
load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

setup_logger()
logger = logging.getLogger('app.services.weaviate.test')


def _safe_eval_pythonish(s: Any) -> Any:
    """
    Try json.loads first (for JSON strings).
    If that fails and the string looks like a Python repr, try ast.literal_eval.
    Otherwise return original value.
    """
    if s is None:
        return None
    if isinstance(s, (dict, list)):
        return s
    if not isinstance(s, str):
        return s
    s_strip = s.strip()
    # Fast path for JSON
    try:
        return json.loads(s_strip)
    except Exception:
        pass
    # Try literal_eval for Python-style reprs (single quotes etc.)
    try:
        return ast.literal_eval(s_strip)
    except Exception:
        # last resort: try to correct common quirks, e.g. single quotes to double quotes
        if s_strip.startswith("'") or "':" in s_strip:
            try:
                json_ish = s_strip.replace("'", "\"")
                return json.loads(json_ish)
            except Exception:
                pass
    # give up
    return s


def _parse_coordinates_field(raw: Any) -> Optional[CoordinatesModel]:
    if raw is None:
        return None
    parsed = _safe_eval_pythonish(raw)
    if isinstance(parsed, CoordinatesModel):
        return parsed
    if isinstance(parsed, dict):
        # accept keys 'lat'/'lng' or 'latitude'/'longitude'
        lat_key = "lat" if "lat" in parsed else ("latitude" if "latitude" in parsed else None)
        lng_key = "lng" if "lng" in parsed else ("longitude" if "longitude" in parsed else None)
        if lat_key and lng_key:
            try:
                return CoordinatesModel(latitude=float(parsed[lat_key]), longitude=float(parsed[lng_key]))
            except ValidationError as e:
                logger.warning(f"Coordinates validation failed: {e}")
                return None
            except Exception:
                return None
        # If dict already matches coordinates keys:
        try:
            return CoordinatesModel(**parsed)
        except Exception:
            return None
    return None


def _parse_reviews_field(raw: Any) -> List[ReviewModel]:
    if raw is None:
        return []
    parsed = _safe_eval_pythonish(raw)
    reviews_list = []
    if isinstance(parsed, list):
        for item in parsed:
            if isinstance(item, ReviewModel):
                reviews_list.append(item)
            elif isinstance(item, dict):
                try:
                    reviews_list.append(ReviewModel(**item))
                except ValidationError as e:
                    logger.debug(f"Skipping invalid review item: {e}")
                    continue
    return reviews_list


def _parse_tags_field(raw: Any) -> List[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    if isinstance(raw, str):
        # try safe eval (handles "['a', 'b']") then fallback to splitting on comma/semicolon
        parsed = _safe_eval_pythonish(raw)
        if isinstance(parsed, list):
            return [str(x).strip() for x in parsed if str(x).strip()]
        # fallback
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        return parts
    return []


def _parse_opening_hours_field(raw: str) -> Optional[OpeningHoursModel]:
    if isinstance(raw, str) and "OpeningHours(" in raw:
        # default value, we don't need it
        return None
    
    # helper to normalize weekly keys to canonical capitalized weekday names
    def _normalize_weekly(weekly_raw: Any) -> Dict[str, Any]:
        weekday_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        normalized = {}
        if not isinstance(weekly_raw, dict):
            return {}
        for k, v in weekly_raw.items():
            if not isinstance(k, str):
                continue
            key_lower = k.strip().lower()
            # find canonical weekday match
            matched = next((d for d in weekday_names if d.lower() == key_lower), None)
            if matched is None:
                # try to title-case unknown keys
                matched = k.strip().title()
            # ensure the value is a list of dicts with start/end
            if isinstance(v, list):
                cleaned_list = []
                for item in v:
                    if isinstance(item, dict):
                        start = item.get("start") or item.get("Start") or item.get("start_time")
                        end = item.get("end") or item.get("End") or item.get("end_time")
                        cleaned_list.append({"start": start, "end": end})
                normalized[matched] = cleaned_list
            else:
                normalized[matched] = v
        # make sure all days exist (avoid missing keys downstream)
        for d in weekday_names:
            if d not in normalized:
                normalized[d] = []
        return normalized

    parsed = _safe_eval_pythonish(raw)
    # If already a model instance
    if isinstance(parsed, OpeningHoursModel):
        return parsed

    # If we got a dict-like structure, normalize and instantiate model
    if isinstance(parsed, dict):
        try:
            if 'weekly' in parsed and isinstance(parsed.get('weekly'), dict):
                parsed['weekly'] = _normalize_weekly(parsed['weekly'])
            # try pydantic validation
            res = OpeningHoursModel(**parsed)
            return res
        except ValidationError as e:
            logger.debug(f"OpeningHoursModel validation failed for dict input: {e}")
            return None
        except Exception as e:
            logger.exception(f"Unexpected error parsing opening hours dict: {e}")
            return None

    # Handle dataclass/repr strings like "OpeningHours(... weekly={...})"

    return None



def _parse_attraction_row(row: Dict[str, Any]) -> Optional[AttractionModel]:
    """
    Convert a single CSV row (as dict of strings) into AttractionModel (pydantic).
    Handles parsing/coercion of coordinates, opening_hours, booleans, tags, rating, price_level, last_updated.
    Returns AttractionModel or None on validation failure.
    """
    try:
        parsed: Dict[str, Any] = {}

        # Required/simple fields (try common CSV column names)
        for csv_key, model_key in [
            ("name", "name"),
            ("city", "city"),
            ("address", "address"),
            ("postal_code", "postal_code"),
            ("administrative_area_level_1", "administrative_area_level_1"),
            ("administrative_area_level_2", "administrative_area_level_2"),
            ("sublocality_level_1", "sublocality_level_1"),
            ("place_id", "place_id"),
        ]:
            if csv_key in row and row[csv_key] != "":
                parsed[model_key] = row[csv_key]

        # maps_url: prefer 'maps_url' but accept legacy 'url'
        maps_url_val = None
        if "maps_url" in row and row["maps_url"] != "":
            maps_url_val = row["maps_url"]
        elif "url" in row and row["url"] != "":
            maps_url_val = row["url"]
        if maps_url_val is not None:
            parsed["maps_url"] = maps_url_val

        # coordinates
        coords_raw = row.get("coordinates") if "coordinates" in row else None
        coords = _parse_coordinates_field(coords_raw)
        if coords is not None:
            parsed["coordinates"] = coords

        # opening_hours
        opening_raw = row.get("opening_hours") if "opening_hours" in row else None
        opening_parsed = _parse_opening_hours_field(opening_raw)
        if opening_parsed is not None:
            parsed["opening_hours"] = opening_parsed

        # reviews
        reviews_raw = row.get("reviews") if "reviews" in row else None
        parsed_reviews = _parse_reviews_field(reviews_raw)
        if parsed_reviews:
            parsed["reviews"] = parsed_reviews

        # tags
        tags_raw = row.get("tags") if "tags" in row else None
        parsed["tags"] = _parse_tags_field(tags_raw)

        # boolean service fields
        bool_fields = [
            "wheelchair_accessible_entrance",
            "serves_beer",
            "serves_breakfast",
            "serves_brunch",
            "serves_dinner",
            "serves_lunch",
            "serves_vegetarian_food",
            "serves_wine",
            "takeout",
        ]
        for b in bool_fields:
            if b in row:
                val = row[b]
                if isinstance(val, str):
                    s = val.strip().lower()
                    parsed[b] = s in {"1", "true", "yes", "y", "t", "on"}
                else:
                    parsed[b] = bool(val)

        # rating / price_level convert
        if row.get("rating"):
            try:
                # allow numeric or string
                parsed["rating"] = float(row["rating"])
            except Exception:
                parsed["rating"] = None
        if row.get("price_level"):
            try:
                parsed["price_level"] = int(float(row["price_level"]))
            except Exception:
                parsed["price_level"] = None

        # phone_number
        if "phone_number" in row and row["phone_number"] != "":
            parsed["phone_number"] = row["phone_number"]

        parsed["last_updated"] = datetime.now(timezone.utc) 

        # Build AttractionModel (pydantic) for validation & normalization
        attraction = AttractionModel(**parsed)
        return attraction
    except ValidationError as e:
        logger.warning(f"CSV row validation failed when building AttractionModel: {e}")
        return None
    except Exception as e:
        logger.exception(f"Unexpected error while parsing attraction CSV row: {e}")
        return None


def _extract_chunk_index(chunk_id: str, emb_meta: EmbeddingMetadataModel) -> int:
    """
    Extract chunk index from chunk_id or embedding metadata.
    Expected format: something like 'chunk_0', 'chunk_1', etc.
    Falls back to parsing from other metadata if available.
    """
    if chunk_id:
        # Try to extract number from chunk_id
        import re
        match = re.search(r'chunk[_\-]?(\d+)', chunk_id.lower())
        if match:
            return int(match.group(1))
        
        # Try to extract just a number at the end
        match = re.search(r'(\d+)$', chunk_id)
        if match:
            return int(match.group(1))
    
    # Fallback: try to extract from source_file if it has numbering
    if hasattr(emb_meta, 'source_file') and emb_meta.source_file:
        match = re.search(r'(\d+)', emb_meta.source_file)
        if match:
            return int(match.group(1))
    
    # Last resort: return 0
    logger.warning(f"Could not extract chunk_index from chunk_id '{chunk_id}', defaulting to 0")
    return 0


class DataLoader:
    def __init__(self, embeddings_dir: Path, metadata_file: Path):
        self.embeddings_dir = Path(embeddings_dir)
        self.metadata_file = Path(metadata_file)
        self.metadata_df: Optional[pd.DataFrame] = None
        self._load_metadata()

    def _load_metadata(self) -> None:
        """Load and cache metadata CSV"""
        try:
            self.metadata_df = pd.read_csv(self.metadata_file, dtype=str).fillna("")
            logger.info(f"Loaded metadata from {self.metadata_file} ({len(self.metadata_df)} rows)")
        except Exception as e:
            logger.error(f"Failed to load metadata: {e}")
            raise

    def _load_embedding_file(self, file_path: Path) -> Optional[Dict]:
        """Load a single embedding JSON file"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load embedding file {file_path}: {e}")
            return None

    def _match_metadata(self, source_file: str, emb_meta: EmbeddingMetadataModel) -> Optional[Dict]:
        """
        Match metadata row in CSV for given source_file.
        Strategies:
          - Try to parse attraction name from source_file (City_Name.txt or City_Name with underscore).
          - Try exact or case-insensitive contains on 'name' column.
          - Try city + contains.
        """
        if self.metadata_df is None or self.metadata_df.empty:
            return None

        basename = Path(source_file).name
        # replace infocorrect naming bug result
        basename = basename.replace(", Lviv", "")
        # attempt to extract name component after first underscore
        parts = basename.split("_", 1)
        attraction_guess = parts[1] if len(parts) > 1 else parts[0]
        # strip file extension
        if attraction_guess.lower().endswith(".txt"):
            attraction_guess = attraction_guess[:-4]
        attraction_guess = attraction_guess.strip().replace(".txt", "")

        # 1) exact (case-insensitive) name match
        df = self.metadata_df
        mask_exact = df["name"].str.lower().str.strip() == attraction_guess.lower().strip()
        if mask_exact.any():
            idx = mask_exact[mask_exact].index[0]
            return df.loc[idx].to_dict()

        # 2) contains match
        mask_contains = df["name"].str.lower().str.contains(attraction_guess.lower().strip(), na=False)
        if mask_contains.any():
            idx = mask_contains[mask_contains].index[0]
            return df.loc[idx].to_dict()

        logger.warning(f"No metadata match for {source_file} (guess='{attraction_guess}')")
        return None

    def load_all(self) -> List[AttractionWithChunks]:
        """
        Load all embedding files, validate them, group by source_file,
        match a single CSV metadata row per source, and return grouped objects.
        """
        files = sorted(self.embeddings_dir.glob("*.json"))
        logger.info(f"Found {len(files)} embedding files in {self.embeddings_dir}")

        # temporary grouping: source_file -> list of validated EmbeddingModel
        grouped: Dict[str, List[EmbeddingModel]] = {}

        for json_file in files:
            raw = self._load_embedding_file(json_file)
            if not raw:
                continue

            # Validate embedding file with EmbeddingModel
            try:
                emb_obj = EmbeddingModel(**raw)
            except ValidationError as e:
                logger.warning(f"Skipping {json_file}: embedding JSON validation error: {e}")
                continue
            except Exception as e:
                logger.exception(f"Unexpected error validating embedding {json_file}: {e}")
                continue

            emb_meta = emb_obj.metadata
            source_file = getattr(emb_meta, "source_file", None)
            if not source_file:
                logger.warning(f"No source_file present in {json_file}'s metadata, skipping")
                continue

            grouped.setdefault(source_file, []).append(emb_obj)

        results: List[AttractionWithChunks] = []
        logger.info(f"Grouped embeddings into {len(grouped)} source_files")
        # For each source_file, match csv metadata once and create chunks
        for source_file, emb_list in grouped.items():
            if source_file == "Kyiv_St. Volodymyr's Cathedral.txt":
                continue
            # use first embedding's metadata for matching heuristics (like city)
            first_meta = emb_list[0].metadata if emb_list else None

            raw_row = None
            attraction_model = None
            logger.info(f"source file: {source_file}")
            try:
                raw_row = self._match_metadata(source_file, first_meta) if first_meta is not None else None
                if raw_row:
                    attraction_model = _parse_attraction_row(raw_row)
                else:
                    raise ValueError("raw metadata row shouldn't be none")
            except Exception as e:
                logger.exception(f"Error matching/parsing CSV metadata for {source_file}: {e}")

            chunks: List[ChunkData] = []
            for idx, emb_obj in enumerate(emb_list):
                emb_meta = emb_obj.metadata
                # Create chunk with denormalized attraction metadata
                chunk = ChunkData(
                    chunk_text=emb_obj.text,
                    embedding=emb_obj.embedding,
                    # Denormalized attraction fields for efficient filtering
                    name=attraction_model.name if attraction_model else None,
                    city=attraction_model.city if attraction_model else getattr(emb_meta, "city", None),
                    administrative_area_level_1=attraction_model.administrative_area_level_1 if attraction_model else None,
                    administrative_area_level_2=attraction_model.administrative_area_level_2 if attraction_model else None,
                    tags=attraction_model.tags if attraction_model else [],
                    rating=attraction_model.rating if attraction_model else None,
                    place_id=attraction_model.place_id if attraction_model else None,
                )
                chunks.append(chunk)

            attraction = AttractionWithChunks(
                source_file=source_file,
                attraction=attraction_model,
                chunks=chunks,
            )
            results.append(attraction)



        logger.info(f"Loaded {len(results)} grouped attractions with chunks")
        return results


if __name__ == "__main__":
    embeddings_dir = Path("data/embeddings")
    metadata_file = Path("data/attractions_metadata.csv")
    loader = DataLoader(embeddings_dir, metadata_file)
    grouped_attractions = loader.load_all()