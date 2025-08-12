"""
Embedding Pipeline for Voyager T800 Travel Assistant
Generates semantic vector embeddings for travel content using OpenAI embeddings.
"""

import argparse
import os
import re
import json
import csv
import time
from openai import OpenAI
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv, find_dotenv 
from typing import List, Dict, Any, Iterable, Optional, Tuple

# Load .env variables early (optional) - kept for OPENAI_API_KEY only
load_dotenv(find_dotenv(), override=False)

# Optional dependencies with fallbacks
try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False

try:
    from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
    TENACITY_AVAILABLE = True
except ImportError:
    TENACITY_AVAILABLE = False


# -------------------------
# Defaults & Constants
# -------------------------
DEFAULT_MODEL = "text-embedding-3-small"
DEFAULT_PROVIDER = "openai"
CLEANING_VERSION = "v1.2"
METADATA_CSV_PATH = "metadata.csv"
SUPPORTED_EXTENSIONS = {".txt", ".json"}
DEFAULT_INPUT_DIR = "data/raw"
DEFAULT_OUTPUT_DIR = "data/embeddings"
DEFAULT_MAX_TOKENS = 450
DEFAULT_OVERLAP = 0.2
DEFAULT_BATCH_SIZE = 64
DEFAULT_POLITE_DELAY = 0.1
DEFAULT_RETRY_ATTEMPTS = 5
DEFAULT_RETRY_MIN_WAIT = 1
DEFAULT_RETRY_MAX_WAIT = 30



# -------------------------
# Text cleaning & tokenization
# -------------------------
def basic_clean(text: str) -> str:
    """Clean and normalize text content."""
    if not text:
        return ""
    # Normalize whitespace
    text = re.sub(r"[\r\t]", " ", text)
    text = re.sub(r"\u00A0", " ", text)
    # Collapse multiple spaces/newlines
    text = re.sub(r"\s+", " ", text).strip()
    # Remove non-informative symbols (keep punctuation, letters, numbers)
    text = re.sub(r"[^\w\s\.,;:!\?\-\(\)/]", "", text)
    return text


def get_encoder():
    """Get tiktoken encoder if available."""
    if not TIKTOKEN_AVAILABLE:
        return None
    try:
        return tiktoken.get_encoding("cl100k_base")
    except Exception as e:
        print(f"Error initializing tiktoken encoder: {e}")
        return None


def tokenize_text(text: str, encoder) -> List[int]:
    """Tokenize text using encoder or fallback to word-based."""
    if encoder is None:
        # Fallback: split by words
        return text.split()
    return encoder.encode(text)


def detokenize_tokens(tokens: List[Any], encoder) -> str:
    """Convert tokens back to text."""
    if encoder is None:
        if isinstance(tokens, list):
            return " ".join(tokens)
        return str(tokens)
    return encoder.decode(tokens)


def sliding_window_chunk_tokens(
    tokens: List[Any], 
    max_tokens: int, 
    overlap_ratio: float
) -> List[List[Any]]:
    """Create overlapping chunks using sliding window approach."""
    if max_tokens <= 0:
        return []
    if not tokens:
        return []
    
    overlap = int(max_tokens * overlap_ratio)
    overlap = min(overlap, max_tokens - 1) if max_tokens > 1 else 0

    chunks: List[List[Any]] = []
    start = 0
    
    while start < len(tokens):
        end = min(start + max_tokens, len(tokens))
        chunks.append(tokens[start:end])
        
        if end == len(tokens):
            break
            
        start = end - overlap if overlap > 0 else end
    
    return chunks

# -------------------------
# I/O utils
# -------------------------
def read_file_content(path: Path) -> str:
    """Read and parse file content based on file type."""
    suffix = path.suffix.lower()
    
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="latin-1", errors="ignore")
    
    if suffix == ".json":
        try:
            data = json.loads(text)
            # If JSON has a top-level "text" field, prefer that
            if isinstance(data, dict) and "text" in data and isinstance(data["text"], str):
                return data["text"]
            # Otherwise, stringify
            return json.dumps(data, ensure_ascii=False)
        except Exception:
            return text
    
    return text


def discover_input_files(input_dir: Path) -> List[Path]:
    """Find all supported input files recursively."""
    all_files: List[Path] = []
    
    for root, _, files in os.walk(input_dir):
        for f in files:
            p = Path(root) / f
            if p.suffix.lower() in SUPPORTED_EXTENSIONS:
                all_files.append(p)
    
    return sorted(all_files)


def load_metadata_mappings(csv_path: Path) -> Tuple[Dict[str, str], Dict[str, str]]:
    """Load metadata CSV and build mappings for city lookup.

    Returns:
      - path_to_city: maps normalized posix file path (e.g., 'data/raw/Kyiv_....txt') -> city
      - basename_to_city: maps basename (e.g., 'Kyiv_....txt') -> city if unique, otherwise omitted
    """
    path_to_city: Dict[str, str] = {}
    basename_counts: Dict[str, int] = {}
    basename_temp: Dict[str, str] = {}

    if not csv_path.exists():
        print(f"Warning: metadata CSV not found at {csv_path}")
        return path_to_city, {}

    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            city = (row.get("city") or "").strip()
            file_path = (row.get("file_path") or "").strip()
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

    basename_to_city: Dict[str, str] = {b: basename_temp[b] for b, c in basename_counts.items() if c == 1}
    return path_to_city, basename_to_city


def infer_city_from_metadata(input_path: Path, path_to_city: Dict[str, str], basename_to_city: Dict[str, str]) -> str:
    """Infer city using metadata.csv mappings with multiple matching strategies."""
    abs_posix = input_path.resolve().as_posix()
    cwd_posix = Path.cwd().as_posix()
    rel_from_cwd = abs_posix
    if abs_posix.startswith(cwd_posix + "/"):
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

    return "unknown"


def ensure_output_dir(output_dir: Path):
    """Create output directory if it doesn't exist."""
    output_dir.mkdir(parents=True, exist_ok=True)


def get_next_global_chunk_id(output_dir: Path) -> int:
    """Return the next global sequential chunk ID based on existing files.

    Scans filenames like '<city>_NNN.json' and returns max(NNN)+1.
    Note: This is O(n) over files in the output directory and is sufficient
    for moderate corpus sizes. For very large directories, consider tracking
    the last ID in a small sidecar file (e.g., 'index.json').
    """
    max_id = 0
    for file_path in output_dir.glob("*.json"):
        stem = file_path.stem
        if "_" not in stem:
            continue
        id_part = stem.split("_")[-1]
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
                api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise RuntimeError("OpenAI API key must be provided in OPENAI_API_KEY environment variable")
            self._client = OpenAI(api_key=api_key)
        except ImportError:
            raise RuntimeError("OpenAI client not available. Install with: pip install openai")

    def embed_batch(self, texts: List[str], retry_attempts: int = None, retry_min_wait: int = None, retry_max_wait: int = None) -> List[List[float]]:
        """Generate embeddings for a batch of texts with retry logic."""
        if not TENACITY_AVAILABLE:
            # Simple retry without tenacity
            return self._embed_batch_simple(texts)
        
        # Use provided values or defaults
        attempts = retry_attempts or DEFAULT_RETRY_ATTEMPTS
        min_wait = retry_min_wait or DEFAULT_RETRY_MIN_WAIT
        max_wait = retry_max_wait or DEFAULT_RETRY_MAX_WAIT
        
        @retry(
            reraise=True,
            stop=stop_after_attempt(attempts),
            wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
            retry=retry_if_exception_type(Exception),
        )
        def _embed_with_retry():
            return self._embed_batch_simple(texts)
        
        return _embed_with_retry()
    
    def _embed_batch_simple(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a batch of texts."""
        response = self._client.embeddings.create(model=self.model, input=texts)
        vectors = [d.embedding for d in response.data]
        return vectors

# -------------------------
# Save/validate chunk
# -------------------------
def validate_embeddings(vectors: List[List[float]], batch_size: int) -> bool:
    """Validate embedding output quality."""
    if not vectors or len(vectors) != batch_size:
        print(f"Error: Expected {batch_size} vectors, got {len(vectors)}")
        return False
    
    # Check dimensional consistency
    dim = len(vectors[0])
    if any(len(v) != dim for v in vectors):
        print(f"Error: Inconsistent vector dimensions. Expected {dim}, got mixed sizes")
        return False
    
    # Check for zero vectors (potential API issues)
    zero_vectors = sum(1 for v in vectors if all(x == 0 for x in v))
    if zero_vectors > 0:
        print(f"Warning: {zero_vectors} zero vectors detected")
    
    return True


def save_chunk_json(
    output_dir: Path,
    city: str,
    chunk_id: int,
    text: str,
    embedding: List[float],
    source_file: str,
    model: str,
):
    """Save chunk data as structured JSON file."""
    filename = f"{city.lower()}_{chunk_id:03d}.json"
    path = output_dir / filename
    
    data = {
        "text": text,
        "embedding": embedding,
        "metadata": {
            "city": city.capitalize(),
            "source_file": source_file,
            "chunk_id": f"{chunk_id:03d}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "embedding_model": model,
            "cleaning_version": CLEANING_VERSION,
            "original_length": len(text),
        },
    }
    
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), 
        encoding="utf-8"
    )

# -------------------------
# High-level processing
# -------------------------
def build_chunks(
    text: str,
    max_tokens: int,
    overlap_ratio: float,
    encoder,
) -> List[str]:
    """Build text chunks with cleaning and tokenization."""
    cleaned = basic_clean(text)
    tokens = tokenize_text(cleaned, encoder)
    
    if not tokens:
        return []
    
    token_chunks = sliding_window_chunk_tokens(
        tokens, 
        max_tokens=max_tokens, 
        overlap_ratio=overlap_ratio
    )
    
    chunks: List[str] = [detokenize_tokens(tc, encoder) for tc in token_chunks]
    return chunks

def process_file(
    provider: EmbeddingProvider,
    input_path: Path,
    output_dir: Path,
    encoder,
    max_tokens: int,
    overlap_ratio: float,
    batch_size: int,
    path_to_city: Dict[str, str],
    basename_to_city: Dict[str, str],
    polite_delay: float = DEFAULT_POLITE_DELAY,
    retry_attempts: int = DEFAULT_RETRY_ATTEMPTS,
    retry_min_wait: int = DEFAULT_RETRY_MIN_WAIT,
    retry_max_wait: int = DEFAULT_RETRY_MAX_WAIT,
) -> Tuple[int, Optional[int]]:
    """Process a single input file and generate embeddings."""
    print(f"Processing: {input_path.name}")
    
    raw_text = read_file_content(input_path)
    if not raw_text:
        print(f"  Warning: No content found in {input_path.name}")
        return 0, None

    chunks = build_chunks(
        raw_text, 
        max_tokens=max_tokens, 
        overlap_ratio=overlap_ratio, 
        encoder=encoder
    )
    
    if not chunks:
        print(f"  Warning: No chunks generated from {input_path.name}")
        return 0, None
        
    city = infer_city_from_metadata(input_path, path_to_city, basename_to_city)
    start_index = get_next_global_chunk_id(output_dir)

    # Process in batches
    total_written = 0
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        
        try:
            vectors = provider.embed_batch(
                batch,
                retry_attempts=retry_attempts,
                retry_min_wait=retry_min_wait,
                retry_max_wait=retry_max_wait
            )
            
            # Validate embeddings
            if not validate_embeddings(vectors, len(batch)):
                print(f"  Error: Validation failed for batch starting at chunk {i}")
                continue
            
            # Save chunks
            for j, (text, vec) in enumerate(zip(batch, vectors)):
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
            print(f"  Processed batch {i//batch_size + 1}: {len(batch)} chunks")
            
            # Polite pacing
            time.sleep(polite_delay)
            
        except Exception as e:
            print(f"  Error processing batch {i//batch_size + 1}: {e}")
            continue

    last_index = start_index + total_written - 1 if total_written > 0 else None
    print(f"  Completed: {total_written} chunks written for city '{city}'")
    
    return total_written, last_index

# -------------------------
# CLI & main
# -------------------------
def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate semantic embeddings for travel content."
    )
    parser.add_argument(
        "--input-dir", 
        type=str, 
        default=str(Path(DEFAULT_INPUT_DIR)), 
        help="Directory with source documents"
    )
    parser.add_argument(
        "--output-dir", 
        type=str, 
        default=str(Path(DEFAULT_OUTPUT_DIR)), 
        help="Directory to write chunk JSON files"
    )
    parser.add_argument(
        "--provider", 
        type=str, 
        default="openai", 
        choices=["openai"], 
        help="Embedding provider"
    )
    parser.add_argument(
        "--model", 
        type=str, 
        default=DEFAULT_MODEL, 
        help="Embedding model name"
    )
    parser.add_argument(
        "--max-tokens", 
        type=int, 
        default=DEFAULT_MAX_TOKENS, 
        help="Max tokens per chunk"
    )
    parser.add_argument(
        "--overlap", 
        type=float, 
        default=DEFAULT_OVERLAP, 
        help="Chunk overlap ratio (0-1)"
    )
    parser.add_argument(
        "--batch-size", 
        type=int, 
        default=DEFAULT_BATCH_SIZE, 
        help="Batch size for embedding API calls"
    )
    return parser.parse_args()


def main():
    """Main execution function."""
    args = parse_args()

    # Resolve params: CLI > code defaults
    input_dir = Path(args.input_dir if args.input_dir else DEFAULT_INPUT_DIR)
    output_dir = Path(args.output_dir if args.output_dir else DEFAULT_OUTPUT_DIR)
    provider = args.provider if args.provider else DEFAULT_PROVIDER
    model = args.model if args.model else DEFAULT_MODEL
    max_tokens = args.max_tokens if args.max_tokens else DEFAULT_MAX_TOKENS
    overlap = args.overlap if args.overlap else DEFAULT_OVERLAP
    batch_size = args.batch_size if args.batch_size else DEFAULT_BATCH_SIZE
    
    if not input_dir.exists():
        print(f"Error: Input directory does not exist: {input_dir}")
        return
    
    ensure_output_dir(output_dir)

    files = discover_input_files(input_dir)
    if not files:
        print(f"No input files found under: {input_dir}")
        print(f"Supported extensions: {', '.join(SUPPORTED_EXTENSIONS)}")
        return

    # Load metadata mappings once
    metadata_csv = Path(DEFAULT_INPUT_DIR).parent / METADATA_CSV_PATH
    path_to_city, basename_to_city = load_metadata_mappings(metadata_csv)

    encoder = get_encoder()
    if not encoder:
        print("Warning: tiktoken not available, using word-based tokenization")

    try:
        # Get API key from environment
        provider_client = EmbeddingProvider(provider=provider, model=model)
    except Exception as e:
        print(f"Error initializing embedding provider: {e}")
        return

    print(f"Processing {len(files)} files...")
    print(f"Chunk size: {max_tokens} tokens, overlap: {overlap:.1%}")
    print(f"Batch size: {batch_size}")
    print(f"Output directory: {output_dir}")
    print("-" * 50)

    total_files = 0
    total_chunks = 0

    for file_path in files:
        try:
            written, last_index = process_file(
                provider=provider_client,
                input_path=file_path,
                output_dir=output_dir,
                encoder=encoder,
                max_tokens=max_tokens,
                overlap_ratio=overlap,
                batch_size=batch_size,
                path_to_city=path_to_city,
                basename_to_city=basename_to_city,
            )
            if written > 0:
                total_files += 1
                total_chunks += written
        except Exception as e:
            print(f"Error processing {file_path.name}: {e}")
            continue

    print("-" * 50)
    print(f"Summary:")
    print(f"  Files processed: {total_files}")
    print(f"  Total chunks written: {total_chunks}")
    print(f"  Output location: {output_dir}")


if __name__ == "__main__":
    main()
