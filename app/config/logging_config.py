#!/usr/bin/env python3
import os
import logging


def setup_logging():
    log_file = os.getenv('INTEGRATION_LOG_FILE_NAME')
    log_level = os.getenv('LOG_LEVEL')
    if not log_file or not log_level:
        raise ValueError("INTEGRATION_LOG_FILE_NAME or LOG_LEVEL environment variable is not set. Please add it to your .env file.")
    
    # Convert log level to uppercase after checking because None will raise an error
    log_level = log_level.upper()
    level = getattr(logging, log_level, logging.INFO)
    
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )

def get_logger(name: str = "voyager_t800"):
    return logging.getLogger(name)
