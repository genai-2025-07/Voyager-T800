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

- Uses a **sliding window** approach to generate overlapping token chunks.
- Configurable parameters:
  - Maximum tokens per chunk (default 450).
  - Overlap ratio (default 20%) to maintain context between chunks.
- Overlap is capped to at most `max_tokens - 1` tokens to avoid empty chunks.
- Chunking is done on token IDs, preserving semantic token boundaries when possible.

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
  - Embedding provider (currently only `"openai"` supported).
  - Model name.
  - Maximum tokens per chunk.
  - Chunk overlap ratio.
  - Batch size.
- Default parameters provide sensible defaults for typical usage.

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