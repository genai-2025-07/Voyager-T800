"""
Embedding Pipeline for Voyager T800 Travel Assistant
Generates semantic vector embeddings for travel content using OpenAI embeddings.
"""

import csv
import json
import logging
import os
import re
import shutil
import tempfile
import time

from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from dotenv import find_dotenv, load_dotenv
from openai import OpenAI

from app.utils.file_utils import read_file_content


# Load .env variable for OPENAI_API_KEY
load_dotenv(find_dotenv(), override=False)

# Optional dependencies with fallbacks
try:
    import tiktoken

    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False

try:
    from tenacity import (
        retry,
        retry_if_exception_type,
        stop_after_attempt,
        wait_exponential,
    )

    TENACITY_AVAILABLE = True
except ImportError:
    TENACITY_AVAILABLE = False


logger = logging.getLogger(__name__)


# -------------------------
# Defaults & Constants
# -------------------------

# Embedding model to use.
# Smaller models (e.g., "text-embedding-3-small") are cheaper and faster but less accurate.
# Larger models (e.g., "text-embedding-3-large") cost more but may yield better semantic matches.
DEFAULT_MODEL = os.getenv('EMBED_MODEL', 'text-embedding-3-small')

# Embedding provider service name (currently supports "openai").
DEFAULT_PROVIDER = os.getenv('EMBED_PROVIDER', 'openai')

# Data cleaning configuration version — helps track preprocessing changes across runs.
# Increment when text cleaning rules are updated.
CLEANING_VERSION = os.getenv('EMBED_CLEANING_VERSION', 'v1.2')

# Path to CSV file with metadata mapping (e.g., city names, source files).
# Should exist in the working directory unless overridden.
METADATA_CSV_PATH = os.getenv('EMBED_METADATA_CSV_PATH', 'data/metadata.csv')

# Input and output directories for embeddings pipeline.
DEFAULT_INPUT_DIR = os.getenv('EMBED_INPUT_DIR', 'data/raw')
DEFAULT_OUTPUT_DIR = os.getenv('EMBED_OUTPUT_DIR', 'data/embeddings')

# Maximum tokens per chunk before splitting (affects chunk size and embedding cost).
# Fewer tokens per chunk → more chunks → higher API calls (more cost).
DEFAULT_MAX_TOKENS = int(os.getenv('EMBED_MAX_TOKENS', 450))

# Overlap ratio between chunks — helps preserve context across chunk boundaries.
# Higher overlap improves semantic continuity but increases number of chunks (and cost).
DEFAULT_OVERLAP = float(os.getenv('EMBED_CHUNK_OVERLAP', 0.2))

# Number of text chunks processed per embedding API request.
# Larger batches → fewer requests (faster, cheaper) but may hit API rate limits or size limits.
DEFAULT_BATCH_SIZE = int(os.getenv('EMBED_BATCH_SIZE', 64))

# Delay (seconds) between embedding requests to avoid hitting rate limits.
DEFAULT_POLITE_DELAY = float(os.getenv('EMBED_POLITE_DELAY', 0.1))

# Method for data chunking: 'sliding' or 'paragraph'.
# 'sliding' - refers to sliding window method.
# 'paragraph' - refers to chunking by papragraph.
DEFAULT_CHUNKING_METHOD = os.getenv('EMBED_CHUNKING_METHOD', 'sliding')

# Retry configuration for failed API calls.
# These affect reliability (more retries) vs. speed (fewer retries).
DEFAULT_RETRY_ATTEMPTS = int(os.getenv('EMBED_RETRY_ATTEMPTS', 5))
DEFAULT_RETRY_MIN_WAIT = float(os.getenv('EMBED_RETRY_MIN_WAIT', 1))
DEFAULT_RETRY_MAX_WAIT = float(os.getenv('EMBED_RETRY_MAX_WAIT', 30))

# Supported input file extensions — determines what files get processed.
# Update when the support for new extensions is provided.
SUPPORTED_EXTENSIONS = {'.txt', '.json'}


# -------------------------
# Text cleaning & tokenization
# -------------------------
def basic_clean(text: str) -> str:
    """Final light clean before embedding.
    Consider a detailed cleaning was performed before"""
    if not text:
        return ''
    # Remove non-whitespace control characters
    text = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]', '', text)
    # Remove empty section titles (==Title== followed by optional whitespace or line breaks)
    text = re.sub(r'==\s*[^=\n]+\s*==\s*(?=(\s|$))', '', text)
    # Replace whitespace control characters (\t, \n, \r) with spaces
    text = re.sub(r'[\t\n\r]', ' ', text)
    # Collapse spaces
    return re.sub(r'\s+', ' ', text).strip()


@lru_cache(maxsize=1)
def get_encoder():
    """Get tiktoken encoder if available (cached)."""
    if not TIKTOKEN_AVAILABLE:
        return None
    try:
        return tiktoken.get_encoding('cl100k_base')
    except Exception as e:
        logger.error(f'Error initializing tiktoken encoder: {e}')
        return None


def tokenize_text(text: str, encoder) -> list[int]:
    """Tokenize text using encoder or fallback to word-based."""
    if encoder is None:
        # Fallback: split by words
        return re.split(r'\s+', text.strip())
    return encoder.encode(text)


def detokenize_tokens(tokens: list[Any], encoder) -> str:
    """Convert tokens back to text."""
    if encoder is None:
        if isinstance(tokens, list):
            return ' '.join(tokens)
        return str(tokens)
    return encoder.decode(tokens)


def sliding_window_chunk_tokens(tokens: list[Any], max_tokens: int, overlap_ratio: float) -> list[list[Any]]:
    """Create overlapping chunks using sliding window approach.
    Edge cases:
    - empty token list → returns []
    - max_tokens <= 0 → returns []
    - tokens shorter than max_tokens → single chunk returned
    - overlap_ratio > 0.5 → creates heavily overlapping chunks
    - very short last chunk → merged with previous if below min_chunk_size
    - max_tokens = 1 → produces single-token chunks"""
    if max_tokens <= 0:
        return []
    if not tokens:
        return []

    overlap = int(max_tokens * overlap_ratio)
    overlap = min(overlap, max_tokens - 1) if max_tokens > 1 else 0

    chunks: list[list[Any]] = []
    start = 0

    min_chunk_size = max(1, max_tokens // 2)

    while start < len(tokens):
        end = min(start + max_tokens, len(tokens))

        if end - start < min_chunk_size:
            # merge with previous chunk if possible
            if chunks:
                chunks[-1].extend(tokens[start:end])
            else:
                chunks.append(tokens[start:end])
            break

        chunks.append(tokens[start:end])

        if end == len(tokens):
            break

        start = end - overlap if overlap > 0 else end

    return chunks


def paragraph_chunking(
    text: str,
    max_tokens: int,
    overlap_ratio: float,
    encoder=None,
    min_tokens: int | None = None,
) -> list[str]:
    """
    Chunk text by paragraphs (separated by double newlines or tags).
    Short paragraphs are merged with neighbors.
    """
    if not text:
        return []

    min_tokens = min_tokens or max(1, max_tokens // 2)

    # Split by paragraphs (double newlines or section markers)
    paragraphs = re.split(r'\n{2,}|==[^=]+==', text)
    paragraphs = [p.strip() for p in paragraphs if p.strip()]

    # Merge small paragraphs
    merged: list[str] = []
    buffer = ''

    for p in paragraphs:
        p_tokens = tokenize_text(p, encoder)
        if len(p_tokens) < min_tokens:
            if buffer:
                buffer += ' ' + p
            else:
                buffer = p
        else:
            if buffer:
                merged.append(buffer.strip())
                buffer = ''
            merged.append(p)

    if buffer:
        merged.append(buffer.strip())

    # Further split large paragraphs by sliding window
    final_chunks: list[str] = []
    for chunk in merged:
        chunk_tokens = tokenize_text(chunk, encoder)
        if len(chunk_tokens) <= max_tokens:
            final_chunks.append(detokenize_tokens(chunk_tokens, encoder))
        else:
            # Use sliding window on large paragraphs
            sw_chunks = sliding_window_chunk_tokens(chunk_tokens, max_tokens, overlap_ratio)
            final_chunks.extend(detokenize_tokens(c, encoder) for c in sw_chunks)

    return final_chunks


# -------------------------
# I/O utils
# -------------------------


def load_metadata_mappings(csv_path: Path) -> tuple[dict[str, str], dict[str, str]]:
    """
    Load metadata CSV and build mappings for city lookup.

    Returns:
      - path_to_city: maps normalized posix file path (e.g., 'data/raw/kyiv_....txt') -> city
      - basename_to_city: maps basename -> city if unique, otherwise omitted
    """
    path_to_city: dict[str, str] = {}
    basename_counts: dict[str, int] = {}
    basename_temp: dict[str, str] = {}

    if not csv_path.exists():
        logger.warning(f'Warning: metadata CSV not found at {csv_path}')
        return path_to_city, {}

    with csv_path.open('r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        required_headers = {'city', 'file_path'}
        if not required_headers.issubset(reader.fieldnames or []):
            raise ValueError(f'Metadata CSV {csv_path} is missing required columns: {required_headers}')

        for row in reader:
            city = (row.get('city') or '').strip()
            file_path = (row.get('file_path') or '').strip()
            if not city or not file_path:
                continue

            rel_path = Path(file_path)
            key_rel = rel_path.as_posix()
            path_to_city[key_rel] = city

            # Also map absolute path resolved from project root (cwd)
            if not rel_path.is_absolute():
                abs_key = (Path.cwd() / rel_path).resolve().as_posix()
                path_to_city[abs_key] = city

            base = rel_path.name
            basename_counts[base] = basename_counts.get(base, 0) + 1
            basename_temp[base] = city

    basename_to_city: dict[str, str] = {b: basename_temp[b] for b, c in basename_counts.items() if c == 1}

    logger.info(f'[Info] Loaded {len(path_to_city)} path-to-city mappings')
    logger.info(f'[Info] Loaded {len(basename_to_city)} unique basename-to-city mappings')

    return path_to_city, basename_to_city


def infer_city_from_metadata(input_path: Path, path_to_city: dict[str, str], basename_to_city: dict[str, str]) -> str:
    """
    Infer city using metadata.csv mappings with multiple matching strategies.
    Attempts:
      1. Exact absolute path
      2. Relative path from current working directory
      3. Basename if unique in metadata
    """
    abs_posix = input_path.resolve().as_posix()
    cwd_posix = Path.cwd().as_posix()
    rel_from_cwd = abs_posix
    if abs_posix.startswith(cwd_posix + '/'):
        rel_from_cwd = abs_posix[len(cwd_posix) + 1 :]

    # Try exact absolute path
    city = path_to_city.get(abs_posix)
    if city:
        return city

    # Try relative to project root
    city = path_to_city.get(Path(rel_from_cwd).as_posix())
    if city:
        return city

    # Fallback to basename if unique in metadata
    base = input_path.name
    city = basename_to_city.get(base)
    if city:
        return city

    # Debug log for failed lookup
    logger.info(f'[Warning] City not found for file: {input_path}')
    logger.info('  Attempted keys:')
    logger.info(f'    Absolute path: {abs_posix}')
    logger.info(f'    Relative path: {rel_from_cwd}')
    logger.info(f'    Basename: {base}')

    return 'unknown'


def get_next_global_chunk_id(output_dir: Path) -> int:
    """
    Return the next global sequential chunk ID based on existing files.

    Scans filenames like '<city>_NNN.json' and returns max(NNN)+1.

    ⚠ PERFORMANCE WARNING:
        - This implementation performs an O(n) scan over all '*.json' files in
          `output_dir`. For large directories containing thousands or millions
          of files, this may become slow.
        - If processing very large datasets, consider tracking the last assigned
          ID in a lightweight sidecar file (e.g., 'index.json') or database to
          avoid repeated directory scans.
    """

    max_id = 0
    for file_path in output_dir.glob('*.json'):
        stem = file_path.stem
        if '_' not in stem:
            continue
        id_part = stem.split('_')[-1]
        if id_part.isdigit():
            try:
                max_id = max(max_id, int(id_part))
            except ValueError:
                continue
    return max_id + 1


# -------------------------
# Embedding Provider
# -------------------------
class EmbeddingProvider:
    """Handles OpenAI embedding API calls."""

    def __init__(self, provider: str, model: str, api_key: str = None):
        self.provider = provider
        self.model = model
        self._client = None

        try:
            if not api_key:
                api_key = os.getenv('OPENAI_API_KEY')
            if not api_key:
                raise RuntimeError('OpenAI API key must be provided in OPENAI_API_KEY environment variable')
            self._client = OpenAI(api_key=api_key)
        except ImportError:
            raise RuntimeError('OpenAI client not available. Install with: pip install openai')

    def embed_batch(
        self,
        texts: list[str],
        retry_attempts: int = None,
        retry_min_wait: int = None,
        retry_max_wait: int = None,
    ) -> list[list[float]]:
        """
        Generate embeddings for a batch of texts with retry logic.

        If `TENACITY_AVAILABLE` is False, a manual exponential backoff retry is used.
        """
        attempts = retry_attempts or DEFAULT_RETRY_ATTEMPTS
        min_wait = retry_min_wait or DEFAULT_RETRY_MIN_WAIT
        max_wait = retry_max_wait or DEFAULT_RETRY_MAX_WAIT

        if TENACITY_AVAILABLE:

            @retry(
                reraise=True,
                stop=stop_after_attempt(attempts),
                wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
                retry=retry_if_exception_type(Exception),
            )
            def _embed_with_retry():
                try:
                    return self._embed_batch_simple(texts)
                except Exception as e:
                    logger.error(
                        f'[ERROR] Embedding batch failed — Batch size: {len(texts)}, '
                        f'Total input length: {sum(len(t) for t in texts)} chars — {e}'
                    )
                    raise

            return _embed_with_retry()

        else:
            # Manual exponential backoff
            delay = min_wait
            for attempt in range(1, attempts + 1):
                try:
                    return self._embed_batch_simple(texts)
                except Exception as e:
                    logger.error(
                        f'[ERROR] Embedding batch failed (attempt {attempt}/{attempts}) — '
                        f'Batch size: {len(texts)}, Total input length: {sum(len(t) for t in texts)} chars — {e}'
                    )
                    if attempt < attempts:
                        logger.info(f'[INFO] Retrying in {delay:.1f}s...')
                        time.sleep(delay)
                        delay = min(delay * 2, max_wait)
                    else:
                        raise

    def _embed_batch_simple(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts."""
        response = self._client.embeddings.create(model=self.model, input=texts)
        vectors = [d.embedding for d in response.data]
        return vectors


# -------------------------
# Save/validate chunk
# -------------------------
def validate_embeddings(vectors: list[list[float]], batch_size: int, dim_tolerance: int = 1) -> bool:
    """
    Validate embedding output quality.
    Args:
        vectors: List of embedding vectors.
        batch_size: Expected number of vectors.
        dim_tolerance: Allowed deviation in vector dimensionality.
            Example: dim_tolerance=1 allows 1535 or 1537 dims if expected is 1536.
    """
    if not vectors or len(vectors) != batch_size:
        logger.error(f'Error: Expected {batch_size} vectors, got {len(vectors)}')
        return False

    # Check dimensional consistency with tolerance
    expected_dim = len(vectors[0])
    for i, v in enumerate(vectors):
        if not (expected_dim - dim_tolerance <= len(v) <= expected_dim + dim_tolerance):
            logger.error(
                f'Error: Inconsistent vector dimensions. Vector {i} has dimension {len(v)}, outside tolerance range.'
            )
            return False

    # Check for zero vectors (potential API issues)
    zero_vectors = sum(1 for v in vectors if all(x == 0 for x in v))
    if zero_vectors > 0:
        logger.warning(f'Warning: {zero_vectors} zero vectors detected')

    return True


def save_chunk_json(
    output_dir: Path,
    city: str,
    chunk_id: int,
    text: str,
    embedding: list[float],
    source_file: str,
    model: str,
):
    """
    Save chunk data as structured JSON file.

    Uses atomic write to avoid partial/corrupted files if interrupted.
    Writes to a temporary file in the same directory, then renames.
    """
    filename = f'{city.lower()}_{chunk_id:03d}.json'
    final_path = output_dir / filename

    data = {
        'text': text,
        'embedding': embedding,
        'metadata': {
            'city': city.capitalize(),
            'source_file': source_file,
            'chunk_id': f'{chunk_id:03d}',
            'timestamp': datetime.now(UTC).isoformat(),
            'embedding_model': model,
            'cleaning_version': CLEANING_VERSION,
            'original_length': len(text),
        },
    }

    output_dir.mkdir(parents=True, exist_ok=True)

    # Atomic write
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=output_dir, delete=False) as tmp_file:
        json.dump(data, tmp_file, ensure_ascii=False, indent=2)
        temp_path = Path(tmp_file.name)

    shutil.move(str(temp_path), str(final_path))


# -------------------------
# High-level processing
# -------------------------
def build_chunks(
    text: str,
    max_tokens: int,
    overlap_ratio: float,
    encoder=None,
    chunking_method: str = DEFAULT_CHUNKING_METHOD,  # "sliding" or "paragraph"
) -> list[str]:
    """
    Build text chunks using the specified method.
    """
    cleaned = basic_clean(text)

    if chunking_method == 'paragraph':
        return paragraph_chunking(cleaned, max_tokens, overlap_ratio, encoder)
    else:
        # Sliding window token-based
        tokens = tokenize_text(cleaned, encoder)
        if not tokens:
            return []
        if len(tokens) <= max_tokens:
            return [detokenize_tokens(tokens, encoder)]
        token_chunks = sliding_window_chunk_tokens(tokens, max_tokens, overlap_ratio)
        return [detokenize_tokens(tc, encoder) for tc in token_chunks]


def process_file(
    provider: EmbeddingProvider,
    input_path: Path,
    output_dir: Path,
    encoder,
    max_tokens: int,
    overlap_ratio: float,
    batch_size: int,
    path_to_city: dict[str, str],
    basename_to_city: dict[str, str],
    polite_delay: float = DEFAULT_POLITE_DELAY,
    retry_attempts: int = DEFAULT_RETRY_ATTEMPTS,
    retry_min_wait: int = DEFAULT_RETRY_MIN_WAIT,
    retry_max_wait: int = DEFAULT_RETRY_MAX_WAIT,
    chunking_method: str = DEFAULT_CHUNKING_METHOD,
) -> tuple[int, int | None]:
    """
    Process a single input file and generate embeddings.
    Steps:
        1. Read file content.
        2. Split content into token-based chunks with optional overlap.
        3. Infer city metadata from file path or basename.
        4. Process chunks in batches, sending them to the embedding provider.
        5. Save embeddings and metadata as JSON files.
    """
    logger.info(f'Processing: {input_path.name}')

    raw_text = read_file_content(input_path)
    if not raw_text:
        logger.warning(f'  Warning: No content found in {input_path.name}')
        return 0, None

    chunks = build_chunks(
        raw_text,
        max_tokens=max_tokens,
        overlap_ratio=overlap_ratio,
        encoder=encoder,
        chunking_method=chunking_method,
    )

    if not chunks:
        logger.warning(f'  Warning: No chunks generated from {input_path.name}')
        return 0, None

    city = infer_city_from_metadata(input_path, path_to_city, basename_to_city)
    start_index = get_next_global_chunk_id(output_dir)

    # Process in batches
    total_written = 0
    file_start_time = time.time()

    for i in range(0, len(chunks), batch_size):
        batch_start_time = time.time()
        batch = chunks[i : i + batch_size]

        try:
            vectors = provider.embed_batch(
                batch,
                retry_attempts=retry_attempts,
                retry_min_wait=retry_min_wait,
                retry_max_wait=retry_max_wait,
            )

            # Validate embeddings
            if not validate_embeddings(vectors, len(batch)):
                logger.error(f'  Error: Validation failed for batch starting at chunk {i}')
                continue

            # Save chunks
            for j, (text, vec) in enumerate(zip(batch, vectors, strict=False)):
                save_chunk_json(
                    output_dir=output_dir,
                    city=city,
                    chunk_id=start_index + total_written + j,
                    text=text,
                    embedding=vec,
                    source_file=input_path.name,
                    model=provider.model,
                )

            total_written += len(batch)
            batch_time = time.time() - batch_start_time
            logger.info(f'  Processed batch {i // batch_size + 1}: {len(batch)} chunks in {batch_time:.2f}s')

            # Polite pacing
            time.sleep(polite_delay)

        except Exception as e:
            logger.error(f'  Error processing batch {i // batch_size + 1}: {e}')
            continue

    last_index = start_index + total_written - 1 if total_written > 0 else None
    file_time = time.time() - file_start_time
    logger.info(f"  Completed: {total_written} chunks written for city '{city}' in {file_time:.2f}s")

    return total_written, last_index


# -------------------------
# CLI & main
# -------------------------
def main():
    """Main function that delegates to the CLI module"""
    from app.cli.embeddings_cli import main as cli_main

    return cli_main()


if __name__ == '__main__':
    import sys

    sys.exit(main())
