#!/usr/bin/env python3
"""
Weaviate Database Setup Script for Voyager-T800

This script sets up the Weaviate vector database with schemas and populates it with attraction data.
It's designed to be run after the Weaviate container is started.

Usage:
    python setup_weaviate.py
"""

import sys

from pathlib import Path


# Add the app directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from app.config.logger.logger import setup_logger
from app.services.weaviate.weaviate_setup import setup_complete_database


def main():
    """Main function to set up Weaviate database."""
    print('=' * 60)
    print('🎯 Voyager-T800 Weaviate Database Setup')
    print('=' * 60)

    # Setup logging
    setup_logger()

    print('🔗 Connecting to Weaviate...')
    print('📊 Setting up schemas...')
    print('📚 Loading attraction data...')

    try:
        # Run complete database setup
        db_manager, client_wrapper, results = setup_complete_database()

        if db_manager is None or client_wrapper is None:
            print('❌ Failed to connect to Weaviate')
            print('💡 Make sure Weaviate container is running: docker compose --profile dev up')
            sys.exit(1)

        if results is None:
            print('❌ Failed to populate database')
            print('💡 Check if data/embeddings and data/attractions_metadata.csv exist')
            sys.exit(1)

        print('✅ Weaviate setup completed successfully!')
        print(f'📈 Inserted attraction groups: {len(results)}')
        print('🎉 You can now use the application with RAG functionality!')

        # Clean up
        if client_wrapper:
            client_wrapper.disconnect()

    except Exception as e:
        print(f'❌ Error during setup: {e}')
        print('💡 Make sure:')
        print('   - Weaviate container is running')
        print('   - data/embeddings directory exists')
        print('   - data/attractions_metadata.csv exists')
        sys.exit(1)


if __name__ == '__main__':
    main()
