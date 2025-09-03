#!/usr/bin/env python3

import sys
from pathlib import Path
from dotenv import load_dotenv
from app.config.logger.logger import setup_logger
import logging

load_dotenv()
setup_logger()
logger = logging.getLogger(__name__)

project_root = Path(__file__).parent.parent

if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))   

try:
    from app.models.llms.basic_workflow.cli import start_cli
except ImportError as e:
    logger.error(f"Error importing start_cli: {e}")
    raise

def main():
    try:
        start_cli()
        
    except KeyboardInterrupt:
        logger.info("\n👋 Application interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Failed to start Voyager T800: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
