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
    def filter(self, record: logging.LogRecord) -> bool:
        record.service = os.getenv('SERVICE_NAME', 'fastapi-service')
        record.request_id = request_id_ctx_var.get() or '-'
        return True


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        req_id = str(uuid.uuid4())
        request_id_ctx_var.set(req_id)
        request.state.request_id = req_id
        response = await call_next(request)
        return response


def setup_logger():
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
