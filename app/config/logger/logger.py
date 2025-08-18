"""
This module sets up a unified logging configuration using Python’s built-in
logging module, reading from a YAML config file.

Configuration:
--------------
- The logger loads its configuration from a YAML file (default: logger.yaml).
- The path can be overridden by setting the environment variable LOGGING_CONFIG_FILE.
- The default logging level is 'INFO', but can be overridden via LOG_LEVEL env var.

YAML Fields Expected:
---------------------
- formatters: Defines JSON formatter with fields such as timestamp, logger name, message, etc.
- filters: Supports filters like `ServiceFilter` and `RequestIdFilter` for structured context.
- handlers: Console/file handlers using the above formatters and filters.
- loggers/root: Sets the logging level and handlers.

Environment Variables:
----------------------
- LOGGING_CONFIG_FILE: Path to the YAML configuration file.
- LOG_LEVEL: Override the default log level (e.g., DEBUG, INFO, WARNING).
- SERVICE_NAME: Used in logs to identify the service emitting the logs.

Usage:
------
There are two types of logger initialization depending on where the code is used:

1. **Entry-point files (e.g. `main.py`, `worker.py`, CLI scripts):**

   You must initialize the logging system at the very beginning of the file:

       from dotenv import load_dotenv
       from app.config.logger.logger import setup_logger

       load_dotenv()
       setup_logger()

   Then you can safely get a logger instance:

       import logging
       logger = logging.getLogger(__name__)
       logger.info("Starting up...")

2. **All other modules (non-entry-point files):**

   Do **not** call `setup_logger()` again. Just retrieve a logger:

       import logging
       logger = logging.getLogger(__name__)

Note:
-----
- If `__name__ == '__main__'`, the logger name will appear as "__main__" in logs.
  For consistent naming in CLI scripts, use:

      logger = logging.getLogger('app.cli.embeddings_cli')

- Always ensure `setup_logger()` is called once per process, and only from entry-points.
"""

import logging
import os
import uuid

from contextvars import ContextVar
from logging.config import dictConfig

import yaml

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


request_id_ctx_var: ContextVar[str | None] = ContextVar('request_id', default=None)


class ServiceFilter(logging.Filter):
    """
    Logging filter that injects contextual metadata into each log record.

    Adds:
    - `service`: The service name from the environment (defaults to 'fastapi-service').
    - `request_id`: A unique ID for each request, pulled from a context variable.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Modify the log record to include `service` and `request_id` fields.

        Args:
            record (logging.LogRecord): The log record to modify.

        Returns:
            bool: Always returns True to keep the record in the log stream.
        """
        record.service = os.getenv('SERVICE_NAME', 'fastapi-service')
        record.request_id = request_id_ctx_var.get() or '-'
        return True


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware that generates a unique request ID for each incoming request.

    The request ID is stored in both:
    - the `request_id_ctx_var` context variable (for logging),
    - the `request.state.request_id` attribute (for app-level access).
    """

    async def dispatch(self, request: Request, call_next):
        """
        Middleware logic that sets the request ID and passes control to the next handler.

        Args:
            request (Request): The incoming FastAPI request.
            call_next (Callable): The next middleware or route handler in the chain.

        Returns:
            Response: The HTTP response from the downstream handler.
        """
        req_id = str(uuid.uuid4())
        request_id_ctx_var.set(req_id)
        request.state.request_id = req_id
        response = await call_next(request)
        return response


def get_request_id(default: str = '-') -> str:
    """
    Retrieve the current request ID from the context variable.

    Args:
        default (str): The fallback value to return if no request ID is set.

    Returns:
        str: The current request ID or the default value.
    """
    return request_id_ctx_var.get() or default


def setup_logger():
    """
    Initializes the application logger using a YAML configuration file.

    - Loads the logging configuration from a file specified by the LOGGING_CONFIG_FILE environment variable.
    - Falls back to `logger.yaml` in the current directory if not specified.
    - Optionally overrides the root logger level using the LOG_LEVEL environment variable.

    Raises:
        FileNotFoundError: If the logging configuration file is not found.
    """
    base_dir = os.path.dirname(__file__)
    config_path = os.path.join(base_dir, os.getenv('LOGGING_CONFIG_FILE', 'logger.yaml'))

    log_level = os.getenv('LOG_LEVEL', 'INFO').upper()

    if not os.path.isfile(config_path):
        raise FileNotFoundError(f'Logger config not found at: {config_path}')

    with open(config_path) as f:
        config = yaml.safe_load(f)

    if 'root' in config:
        config['root']['level'] = log_level

    dictConfig(config)
