"""
Command-line interface for the embeddings pipeline.
This module handles CLI argument parsing, validation, and orchestration.
"""

import argparse
import logging
import sys

from pathlib import Path

from dotenv import load_dotenv

from app.config.logger.logger import setup_logger
from app.retrieval.embedding.generate_embeddings import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_INPUT_DIR,
    DEFAULT_MAX_TOKENS,
    DEFAULT_MODEL,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_OVERLAP,
    DEFAULT_POLITE_DELAY,
    DEFAULT_PROVIDER,
    DEFAULT_RETRY_ATTEMPTS,
    DEFAULT_RETRY_MAX_WAIT,
    DEFAULT_RETRY_MIN_WAIT,
    METADATA_CSV_PATH,
    SUPPORTED_EXTENSIONS,
    EmbeddingProvider,
    get_encoder,
    load_metadata_mappings,
    process_file,
)
from app.utils.file_utils import discover_input_files


load_dotenv()
setup_logger()
logger = logging.getLogger('app.cli.embeddings_cli')


def create_argument_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser for the embeddings CLI."""
    parser = argparse.ArgumentParser(description='Generate semantic embeddings for travel content')

    # File paths
    parser.add_argument(
        '--input-dir',
        type=str,
        default=str(DEFAULT_INPUT_DIR),
        help='Directory with source documents',
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default=str(DEFAULT_OUTPUT_DIR),
        help='Directory to write chunk JSON files',
    )
    parser.add_argument(
        '--metadata-csv-path',
        type=str,
        default=str(METADATA_CSV_PATH),
        help='Path to the metadata CSV file storing chunk metadata',
    )

    # Provider/model
    parser.add_argument(
        '--provider',
        type=str,
        default=DEFAULT_PROVIDER,
        choices=['openai'],
        help='Embedding provider',
    )
    parser.add_argument('--model', type=str, default=DEFAULT_MODEL, help='Embedding model name')

    # Chunking
    parser.add_argument(
        '--max-tokens',
        type=int,
        default=DEFAULT_MAX_TOKENS,
        help='Max tokens per chunk',
    )
    parser.add_argument(
        '--overlap',
        type=float,
        default=DEFAULT_OVERLAP,
        help='Chunk overlap ratio (0-1)',
    )

    # Batch & retries
    parser.add_argument(
        '--batch-size',
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help='Batch size for embedding API calls',
    )
    parser.add_argument(
        '--retry-attempts',
        type=int,
        default=DEFAULT_RETRY_ATTEMPTS,
        help='Number of retry attempts for failed API calls',
    )
    parser.add_argument(
        '--retry-min-wait',
        type=int,
        default=DEFAULT_RETRY_MIN_WAIT,
        help='Minimum wait time between retries (seconds)',
    )
    parser.add_argument(
        '--retry-max-wait',
        type=int,
        default=DEFAULT_RETRY_MAX_WAIT,
        help='Maximum wait time between retries (seconds)',
    )
    parser.add_argument(
        '--chunking-method',
        type=str,
        default=DEFAULT_RETRY_MAX_WAIT,
        choices=['slide', 'paragraph'],
        help="Method for data chunking: 'sliding' or 'paragraph'",
    )
    parser.add_argument(
        '--polite-delay',
        type=float,
        default=DEFAULT_POLITE_DELAY,
        help='Delay (seconds) between batch API calls to avoid rate limits',
    )

    return parser


def validate_arguments(args: argparse.Namespace) -> bool:
    """
    Validate command-line arguments.

    Args:
        args: Parsed command-line arguments

    Returns:
        bool: True if arguments are valid, False otherwise
    """
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    metadata_file = Path(args.metadata_csv_path)
    batch_size = args.batch_size
    max_tokens = args.max_tokens
    overlap = args.overlap
    retry_attempts = args.retry_attempts
    retry_min_wait = args.retry_min_wait
    retry_max_wait = args.retry_max_wait
    polite_delay = args.polite_delay

    valid = True

    # Input directory
    if not input_dir.exists() or not input_dir.is_dir():
        logger.error(f"Error: Input directory '{input_dir}' does not exist or is not a directory")
        valid = False
    else:
        # Check for supported files
        supported_files = [f for f in input_dir.rglob('*') if f.suffix.lower() in SUPPORTED_EXTENSIONS]
        if not supported_files:
            logger.error(f"Error: No supported files found in '{input_dir}'")
            logger.error(f'Supported extensions: {", ".join(SUPPORTED_EXTENSIONS)}')
            valid = False

    # Output directory
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        test_file = output_dir / '.write_test'
        test_file.write_text('test')
        test_file.unlink()
    except Exception as e:
        logger.error(f"Error: Cannot write to output directory '{output_dir}': {e}")
        valid = False

    # Metadata CSV
    if not metadata_file.exists():
        logger.error(f"Error: Metadata CSV '{metadata_file}' not found")
        valid = False

    # Numeric argument validations
    if max_tokens <= 0:
        logger.error('Error: --max-tokens must be greater than 0')
        valid = False
    if not 0 <= overlap < 1:
        logger.error('Error: --overlap must be in [0, 1)')
        valid = False
    if batch_size <= 0:
        logger.error('Error: --batch-size must be greater than 0')
        valid = False
    if retry_attempts < 0:
        logger.error('Error: --retry-attempts cannot be negative')
        valid = False
    if retry_min_wait < 0 or retry_max_wait < 0:
        logger.error('Error: --retry-min-wait and --retry-max-wait cannot be negative')
        valid = False
    if polite_delay < 0:
        logger.error('Error: --polite-delay cannot be negative')
        valid = False

    return valid


def run_embedding_pipeline(args: argparse.Namespace) -> bool:
    """Run the embedding pipeline with the given arguments."""
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)

    # Discover files
    files = sorted(discover_input_files(input_dir, SUPPORTED_EXTENSIONS))
    if not files:
        logger.error(f'No input files found under: {input_dir}')
        logger.error(f'Supported extensions: {", ".join(SUPPORTED_EXTENSIONS)}')
        return False

    # Load metadata
    metadata_csv = Path(DEFAULT_INPUT_DIR).parent / 'metadata.csv'
    path_to_city, basename_to_city = load_metadata_mappings(metadata_csv)

    encoder = get_encoder()
    if not encoder:
        logger.warning('Warning: tiktoken not available, using word-based tokenization')

    try:
        provider_client = EmbeddingProvider(provider=args.provider, model=args.model)
    except Exception as e:
        logger.error(f'Error initializing embedding provider: {e}')
        return False

    total_files = 0
    total_chunks = 0

    for file_path in files:
        try:
            written, _ = process_file(
                provider=provider_client,
                input_path=file_path,
                output_dir=output_dir,
                encoder=encoder,
                max_tokens=args.max_tokens,
                overlap_ratio=args.overlap,
                batch_size=args.batch_size,
                path_to_city=path_to_city,
                basename_to_city=basename_to_city,
                polite_delay=args.polite_delay,
                retry_attempts=args.retry_attempts,
                retry_min_wait=args.retry_min_wait,
                retry_max_wait=args.retry_max_wait,
                chunking_method=args.chunking_method,
            )
            if written > 0:
                total_files += 1
                total_chunks += written
        except Exception as e:
            logger.error(f'Error processing {file_path.name}: {e}')
            continue

    logger.info('-' * 50)
    logger.info('Summary:')
    logger.info(f'Files processed: {total_files}')
    logger.info(f'Total chunks written: {total_chunks}')
    logger.info(f'Output directory: {output_dir}')
    return True


def main() -> int:
    """
    Main CLI entry point.

    Returns:
        int: Exit code (0 for success, 1 for failure)
    """
    parser = create_argument_parser()
    args = parser.parse_args()

    if not validate_arguments(args):
        return 1

    if run_embedding_pipeline(args):
        logger.info('Embedding pipeline completed successfully!')
        return 0
    else:
        logger.error('Embedding pipeline failed!')
        return 1


if __name__ == '__main__':
    sys.exit(main())
