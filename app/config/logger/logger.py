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
from pathlib import Path

from contextvars import ContextVar
from logging.config import dictConfig

import yaml

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


request_id_ctx_var: ContextVar[str | None] = ContextVar('request_id', default=None)
formatter_str = '%(asctime)s %(levelname)s %(name)s %(message)s %(service)s %(request_id)s'

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
    Robust to missing YAML: falls back to a minimal file+console logging config.
    """
    base_dir = Path(__file__).parent  # app/config/logger
    config_path = base_dir / os.getenv('LOGGING_CONFIG_FILE', 'logger.yaml')

    log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
    log_dir_env = os.getenv('LOG_DIR', './logs')
    log_dir = Path(log_dir_env)
    log_dir.mkdir(parents=True, exist_ok=True)

    # If config file does not exist — fall back to basic config that writes to file+console
    if not config_path.is_file():
        # minimal fallback that still attaches ServiceFilter
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, log_level, logging.INFO))

        # console handler
        ch = logging.StreamHandler()
        ch.setLevel(getattr(logging, log_level, logging.INFO))
        ch.setFormatter(logging.Formatter(formatter_str))
        root_logger.addHandler(ch)

        # file handler
        fh = logging.FileHandler(str(log_dir / 'app.log'))
        fh.setLevel(getattr(logging, log_level, logging.INFO))
        fh.setFormatter(logging.Formatter(formatter_str))
        root_logger.addHandler(fh)

        # add ServiceFilter so `service` and `request_id` fields exist
        root_logger.addFilter(ServiceFilter())
        return

    # load YAML config, and if it includes a 'file' handler, ensure filename is inside LOG_DIR
    with open(config_path) as f:
        config = yaml.safe_load(f)

    # override root level if present
    if 'root' in config:
        config['root']['level'] = log_level

    # ensure handlers.file.filename points to LOG_DIR if a file handler exists
    if isinstance(config, dict) and 'handlers' in config:
        handlers = config['handlers']
        # If you declared a handler named 'file' in YAML, replace its filename with LOG_DIR
        if 'file' in handlers:
            filename = handlers['file'].get('filename', 'app.log')
            handlers['file']['filename'] = str(Path(log_dir) / filename)

    dictConfig(config)