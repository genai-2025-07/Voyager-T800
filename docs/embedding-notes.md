# Embedding Pipeline Notes

_Last updated: August 12, 2025_

This document records architectural and implementation decisions for the semantic embedding pipeline used in the Voyager T800 Travel Assistant project. It covers text processing, chunking, embedding generation, metadata handling, and other design choices.

---

## 1. Overview

- **Purpose:** Generate semantic vector embeddings for travel-related content using OpenAI embeddings.
- **Input:** Raw text files (`.txt`), JSON files and csv files containing related data.
- **Output:** Chunked text embeddings saved as JSON files with structured metadata.

---

## 2. Embedding Provider

- Uses **OpenAI's embedding API** via the official OpenAI Python client.
- Embedding model default: `"text-embedding-3-small"`.
- API key is loaded from the `OPENAI_API_KEY` environment variable.
- Supports batching with configurable batch size (default 64).
- Implements **retry logic** with exponential backoff using the `tenacity` library if available.
- Gracefully falls back to a simple retry mechanism if `tenacity` is not installed.

We chose `"text-embedding-3-small"` because:
- it produces high-quality embeddings suitable for similarity search, clustering, and retrieval;
- embedding vectors have 1,536 dimensions, balancing accuracy with reduced storage and memory requirements;
- significantly lower token cost compared to larger models;
- faster inference times;
- performs well across varied travel-related content (destination descriptions, itinerary details, reviews) without fine-tuning.


Move to the large model if:
- maximum semantic accuracy is needed (e.g., nuanced legal/medical content).
- Your dataset is small enough that cost and storage are not concerns.
- retrieval precision is more critical than speed (e.g., expert search systems).


---

## 3. Text Cleaning & Tokenization

- Basic cleaning (`basic_clean` function):
  - Normalizes whitespace and removes non-informative symbols except punctuation, letters, and numbers.
  - Removes control characters like carriage returns and tabs.
  - Collapses multiple spaces and newlines into a single space.
- Tokenization:
  - Uses `tiktoken` (if installed) with `"cl100k_base"` encoding to tokenize text at the byte-pair encoding level.
  - If `tiktoken` is unavailable, falls back to simple whitespace tokenization.
- Detokenization supports reversing tokens back into text for chunk reconstruction.

---

## 4. Chunking Strategy

Supports two methods for splitting text into chunks before embedding:

1. **Sliding Window (default)**

- Splits text based on a maximum token size (default 450 tokens).
  - value 450 is chosen to balance semantic completeness with API efficiency. Also it Helps avoid cutting off sentences too often while still producing manageable chunks for search indexing. 
- Uses overlapping windows (default 20%) to preserve context across chunks.
  - enough to preserve continuity for ideas that span chunk boundaries without excessive duplication and it is a common practice in semantic search pipelines (typical range: 10–25%).
- Works well for free-flowing text without clear structural markers.
- Overlap is capped to at most max_tokens - 1 tokens to avoid empty chunks.

2. **Paragraph-based (structure-aware)**
- Detects paragraph or section boundaries (e.g., ==Heading== markers).
- Small paragraphs are merged with adjacent ones to meet the minimum token threshold.
- Large paragraphs are further split using a sliding window.
- Designed for structured documents (e.g., Wikipedia-style travel articles) where section boundaries should be respected.

Both methods preserve semantic token boundaries when possible and ensure no chunk exceeds the max_tokens limit.

---

## 5. Input File Handling

- Supports `.txt` files.
- For JSON files:
  - Attempts to extract `"text"` field if present.
  - Otherwise, serializes the entire JSON content as a string.
- Reads files with UTF-8 encoding by default, falls back to Latin-1 with error ignoring if decoding fails.
- Discovers files recursively under a given input directory.
- Warns if no files with supported extensions are found.

---

## 6. Metadata Handling

- Uses a `metadata.csv` file to map file paths and basenames to city names.
- Supports resolving city by:
  - Exact absolute file path match.
  - Relative file path match from project root.
  - Unique basename match if multiple files share the same basename.
- Falls back to `"unknown"` city if no metadata mapping found.
- Metadata enriches embedding JSON outputs with:
  - City name (capitalized).
  - Source filename.
  - Chunk ID.
  - ISO8601 UTC timestamp of embedding generation.
  - Embedding model name.
  - Cleaning version (currently `"v1.2"`).
  - Original chunk text length.

---

## 7. Output Storage & Naming

- Outputs embedding chunks as JSON files in the specified output directory.
- Filenames use the pattern: `{city}_{chunk_id:03d}.json` (e.g., `kyiv_001.json`).
- Chunk IDs are globally sequential within the output directory, determined by scanning existing files and incrementing the highest ID.
- JSON output contains:
  - The chunk text.
  - Embedding vector.
  - Metadata object as described above.
- Output directory is created if it doesn't exist.

---

## 8. Embedding Validation

- After generating embeddings, the pipeline validates:
  - Correct number of vectors returned matches batch size.
  - Consistent vector dimensionality across all vectors in batch.
  - Checks for zero vectors (warning logged if any found, as this may indicate API issues).
- Validation failures result in skipping that batch's output saving.

---

## 9. Processing Flow

- For each input file:
  1. Read and clean text.
  2. Tokenize and chunk text with overlap.
  3. Infer city from metadata.
  4. Generate embeddings for chunks in batches.
  5. Validate and save each chunk embedding with metadata.
  6. Respect a polite delay between batch calls to avoid API rate limits.
- Provides informative progress and error logging via `print()` statements.
- Batch embedding calls support retry on failure, configurable retry parameters.

---

## 10. CLI Interface

- Command-line arguments allow configuring:
  - Input directory (`--input-dir`).
  - Output directory (`--output-dir`).
  - Metadata CSV file path (`--metadata-csv-path`).
  - Embedding provider (currently only `"openai"` supported) (`--provider`).
  - Model name (`--model`).
  - Maximum tokens per chunk (`--max-tokens`).
  - Chunk overlap ratio (`--overlap`).
  - Batch size (`--batch-size`).
  - Retry attempts (`--retry-attempts`).
  - Minimum retry wait in seconds (`--retry-min-wait`).
  - Maximum retry wait in seconds (`--retry-max-wait`).
  - Polite delay between batch API calls in seconds (`--polite-delay`).

### 10.1 CLI Usage Examples

Below are example commands for running the embedding pipeline from the command line.
Defaults can be overridden using CLI arguments or environment variables (see section 11 for .env usage).

**Basic Example**

Generate embeddings from the default input directory (`data/raw`) and save to the default output directory (`data/embeddings`):
```
python -m app.retrieval.embedding.generate_embedding
```
**Specifying Input and Output Directories:**

```
python -m app.retrieval.embedding.generate_embeddings \
    --input-dir ./my_input_texts \
    --output-dir ./my_embeddings
```

**Setting Metadata CSV Path:**
```
python -m app.retrieval.embedding.generate_embeddings \
    --metadata-csv-path ./data/metadata.csv
```
**Adjusting Performance Parameters**

Example with custom batch size, overlap, and polite delay (in seconds):
```
python -m app.retrieval.embedding.generate_embeddings \
    --batch-size 32 \
    --overlap 0.15 \
    --polite-delay 0.2
```

**Using Paragraph-based Chunking:**
```
python -m app.retrieval.embedding.generate_embeddings \
    --output-dir data/embeddings \
    --chunking-method paragraph
```

**Using Environment Variables**

You can set parameters via a .env file or directly in your shell:
```
export OPENAI_API_KEY="sk-..."
export DEFAULT_BATCH_SIZE=32
export METADATA_CSV_PATH="./custom_metadata.csv"
python -m app.embedding.generate_embeddings
```
### Full Option List

| Argument              | Default                  | Description                                              |
| --------------------- | ------------------------ | -------------------------------------------------------- |
| `--input-dir`         | `data/raw`               | Directory containing input text/JSON files               |
| `--output-dir`        | `data/embeddings`        | Directory to save embedding JSON files                   |
| `--metadata-csv-path` | `metadata.csv`           | Path to metadata CSV file                                |
| `--provider`          | `openai`                 | Embedding provider (currently only `"openai"` supported) |
| `--model`             | `text-embedding-3-small` | Embedding model name                                     |
| `--max-tokens`        | `450`                    | Maximum tokens per chunk                                 |
| `--overlap`           | `0.2`                    | Overlap ratio between chunks                             |
| `--batch-size`        | `64`                     | Number of chunks per API call                            |
| `--polite-delay`      | `0.1`                    | Delay between API calls (seconds)                        |
| `--retry-attempts`    | `5`                      | Max retry attempts per batch                             |
| `--retry-min-wait`    | `1`                      | Minimum wait between retries (seconds)                   |
| `--retry-max-wait`    | `30`                     | Maximum wait between retries (seconds)                   |
| `--chunking-method`    | `slide`                     | Chunking method (currently only `"slide"` and `"paragraph"` supported)                   |
---

## 11. Dependency Management & Environment

- Optional dependencies:
  - `tiktoken` for improved tokenization.
  - `tenacity` for robust retrying.
- Environment variables loaded via `python-dotenv` (only for `OPENAI_API_KEY`).
- Uses Python 3 type hints for clarity.
- Relies on standard libraries and well-known packages for robustness and maintainability.

---

## 12. Future Considerations

- For very large output directories, tracking the last chunk ID in a sidecar file (e.g., `chunk_index.json`) could improve performance.
- Extend support for other embedding providers or models.
- Enhance text cleaning for specific domain needs.
- Improve metadata inference with fuzzy matching or more attributes.
- Add logging framework instead of print statements for better observability.
- Add more sophisticated error handling and reporting.

---

*Document prepared by Voyager T800 development team.*