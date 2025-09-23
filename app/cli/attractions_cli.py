"""
Command-line interface for the attractions parser.
This module handles CLI argument parsing and orchestration.
"""

import argparse
import logging
import sys

from pathlib import Path

from app.config.logger.logger import setup_logger
from app.retrieval.parsing.attractions_wiki_parser import AttractionsParser


setup_logger()
logger = logging.getLogger('app.cli.attractions_cli')


def create_argument_parser() -> argparse.ArgumentParser:
    """
    Create and configure the argument parser for the attractions CLI.

    Returns:
        argparse.ArgumentParser: Configured argument parser
    """
    parser = argparse.ArgumentParser(
        description='Attractions Wiki Parser - Extract and clean Wikipedia content for attractions'
    )

    parser.add_argument(
        '--debug', action='store_true', help='Enable debug mode with additional logging and file output'
    )

    parser.add_argument(
        '--output-dir', type=str, default='data/raw', help='Directory to create raw folder (default: data/raw)'
    )

    parser.add_argument(
        '--metadata', type=str, default='data/metadata.csv', help='Path to metadata.csv (default: data/metadata.csv)'
    )

    parser.add_argument(
        '--csv-file',
        type=str,
        default='data/attractions_names_list.csv',
        help='Path to attractions CSV file (default: data/attractions_names_list.csv)',
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
    # Check if CSV file exists
    if not Path(args.csv_file).exists():
        logger.error(f"Error: CSV file '{args.csv_file}' not found")
        return False

    # Check if output directory can be created
    try:
        Path(args.output_dir).mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.error(f"Error: Cannot create output directory '{args.output_dir}': {e}")
        return False

    return True


def run_extraction_with_args(args: argparse.Namespace) -> bool:
    """
    Run the extraction process with the given arguments.

    Args:
        args: Parsed command-line arguments

    Returns:
        bool: True if extraction was successful, False otherwise
    """
    try:
        # Create parser instance
        attractions_parser = AttractionsParser(
            csv_file=args.csv_file, debug_mode=args.debug, output_dir=args.output_dir, metadata_file=args.metadata
        )

        # Run extraction
        attractions_parser.run_extraction()
        return True

    except Exception as e:
        logger.error(f'Error during extraction: {e}')
        return False


def main() -> int:
    """
    Main CLI entry point.

    Returns:
        int: Exit code (0 for success, 1 for failure)
    """
    parser = create_argument_parser()
    args = parser.parse_args()

    # Validate arguments
    if not validate_arguments(args):
        return 1

    # Run extraction
    if run_extraction_with_args(args):
        logger.info('Extraction completed successfully!')
        return 0
    else:
        logger.error('Extraction failed!')
        return 1


if __name__ == '__main__':
    sys.exit(main())
