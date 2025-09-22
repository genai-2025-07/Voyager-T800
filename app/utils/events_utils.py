import json
import re
import logging
from datetime import datetime, timezone
from typing import Any, List, Dict
from app.utils.read_prompt_from_file import read_prompt_from_file

from pydantic import ValidationError
from app.utils.date_utils import preprocess_dates
from app.services.events.models import EventQuery

logger = logging.getLogger(__name__)


def build_query(
    city: str, start_date: datetime, end_date: datetime, categories: list[str]
) -> str:
    """
    Build a query string for event search using a template file.

    Args:
        city: Destination city name
        start_date: Start date for event search
        end_date: End date for event search
        categories: List of event categories to search for

    Returns:
        Formatted query string

    Raises:
        ValueError: If required parameters are invalid
        FileNotFoundError: If template file cannot be found
        KeyError: If template formatting fails
    """
    logger.info(
        f"Building query for city: {city}, date range: {start_date} to {end_date}, categories: {categories}"
    )

    try:
        # Validate input parameters
        if not city or not city.strip():
            raise ValueError("City name cannot be empty")

        if not categories:
            logger.warning("No categories provided, using default")
            categories = ["events"]

        if start_date > end_date:
            raise ValueError("Start date cannot be after end date")

        # Join categories
        categories_str = ", ".join(categories)
        logger.debug(f"Formatted categories: {categories_str}")

        # Read template from file
        try:
            template = read_prompt_from_file("app/prompts/events_query_template.txt")
            logger.debug("Successfully loaded query template")
        except FileNotFoundError as e:
            logger.error(f"Template file not found: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to read template file: {e}")
            raise

        # Format the template with the provided parameters
        try:
            formatted_query = template.format(
                categories=categories_str,
                city=city.strip(),
                start_date=start_date.strftime("%B %d"),
                end_date=end_date.strftime("%B %d"),
            )
            logger.info("Successfully built query string")
            return formatted_query

        except KeyError as e:
            logger.error(f"Template formatting failed - missing placeholder: {e}")
            raise ValueError(f"Template formatting error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error during template formatting: {e}")
            raise

    except Exception as e:
        logger.error(f"Failed to build query: {e}")
        raise


def parse_event_query(user_input: str, structured_llm) -> EventQuery | None:
    """
    Try to parse an EventQuery from user input.
    If dates are missing, enrich with pre-processed hints.
    """
    try:
        hints = preprocess_dates(user_input)

        # Pass today's date as contextual hint to the parser to reduce wrong-year outputs
        current_date = datetime.now(timezone.utc).date()
        augmented_input = (
            f"{user_input}\n\n"
            f"Note: The current year is {current_date.year}. Make sure the start date corresponds to the current year.\n"
            f"If the user doesn't state a specific date, set start_date to today's date {current_date} and set end_date accordingly (use duration if provided, otherwise equal to start_date)."
        )
        query = structured_llm.invoke(augmented_input)

        # Enrich dates if missing
        if not query.start_date and hints.get("start_date"):
            query.start_date = hints["start_date"]
        if not query.end_date and hints.get("end_date"):
            query.end_date = hints["end_date"]

        return query

    except ValidationError as e:
        logging.warning(f"Invalid EventQuery schema, skipping. Error: {e}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error in EventQuery parsing: {e}")
        return None


def extract_events(raw: str) -> List[Dict[str, Any]]:
    """
    Extract event data from raw text response.

    Attempts multiple parsing strategies:
    1. JSON blocks with ```json``` fences
    2. Generic code blocks with ``` fences
    3. Raw JSON arrays in the text

    Args:
        raw: Raw text response containing event data

    Returns:
        List of event dictionaries, empty list if parsing fails

    Raises:
        ValueError: If input is invalid
    """
    logger.info("Starting event extraction from raw text")

    if not raw or not isinstance(raw, str):
        logger.warning("Empty or invalid raw input provided")
        return []

    logger.debug(f"Raw input length: {len(raw)} characters")

    def _try_parse_json(text: str) -> Any:
        """Helper function to safely parse JSON with error logging."""
        try:
            text = text.strip()
            if text.startswith("json\n"):
                text = text[5:]
            parsed = json.loads(text)
            logger.debug(f"Successfully parsed JSON block of length {len(text)}")
            return parsed
        except json.JSONDecodeError as e:
            logger.debug(f"JSON parsing failed: {e}")
            return None
        except Exception as e:
            logger.debug(f"Unexpected parsing error: {e}")
            return None

    # Strategy 1: Look for JSON blocks with ```json``` fences
    logger.debug("Attempting to parse JSON blocks with ```json``` fences")
    try:
        fenced_json_blocks = re.findall(r"```json\s*([\s\S]*?)```", raw, re.IGNORECASE)
        logger.debug(f"Found {len(fenced_json_blocks)} JSON-fenced blocks")

        for i, block in enumerate(fenced_json_blocks):
            logger.debug(f"Processing JSON block {i+1}")
            parsed = _try_parse_json(block)
            if parsed:
                if isinstance(parsed, list):
                    logger.info(
                        f"Successfully extracted {len(parsed)} events from JSON-fenced block"
                    )
                    return parsed
                elif isinstance(parsed, dict):
                    logger.info("Successfully extracted 1 event from JSON-fenced block")
                    return [parsed]
    except Exception as e:
        logger.warning(f"Error processing JSON-fenced blocks: {e}")

    # Strategy 2: Look for generic code blocks with ``` fences
    logger.debug("Attempting to parse generic code blocks with ``` fences")
    try:
        fenced_blocks = re.findall(r"```\s*([\s\S]*?)```", raw)
        logger.debug(f"Found {len(fenced_blocks)} generic-fenced blocks")

        for i, block in enumerate(fenced_blocks):
            logger.debug(f"Processing generic block {i+1}")
            parsed = _try_parse_json(block)
            if parsed:
                if isinstance(parsed, list):
                    logger.info(
                        f"Successfully extracted {len(parsed)} events from generic-fenced block"
                    )
                    return parsed
                elif isinstance(parsed, dict):
                    logger.info("Successfully extracted 1 event from generic-fenced block")
                    return [parsed]
    except Exception as e:
        logger.warning(f"Error processing generic-fenced blocks: {e}")

    # Strategy 3: Look for raw JSON arrays in the text
    logger.debug("Attempting to parse raw JSON arrays in text")
    try:
        parsed = json.loads(re.search(r"\[.*\]", raw, re.DOTALL).group(0))
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):
            return [parsed]
    except Exception as e:
        logger.warning(f"Error processing raw JSON arrays: {e}")

    logger.warning("All parsing strategies failed, returning empty list")
    return []
