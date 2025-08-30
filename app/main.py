import logging

from contextlib import asynccontextmanager
from os import getenv

import uvicorn

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import itinerary
from app.config.config import settings
from app.config.logger.logger import RequestIDMiddleware, setup_logger


setup_logger()
logger = logging.getLogger(__name__)

# Fail fast if required AWS credentials are missing
missing_aws = [v for v in ('AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_REGION') if not getenv(v)]
if missing_aws:
    error_msg = f'Missing required AWS environment variables: {", ".join(missing_aws)}'
    logger.error(error_msg)
    logger.error('Application cannot start without AWS credentials. Please export them in the shell.')
    raise RuntimeError(error_msg)


app = FastAPI()
app.add_middleware(RequestIDMiddleware)


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa ARG001
    """Application lifespan manager for startup and shutdown events."""

    # TODO: Initialize database connections

    server_url = f'http://{settings.host}:{settings.port}'
    logger.info(f'Voyager-T800 is running at {server_url}')

    yield

    # Shutdown
    # TODO: Close database connections
    logger.info('Application shutdown complete')


app = FastAPI(
    title=settings.app_name,
    description=settings.app_description,
    version=settings.app_version,
    debug=settings.debug,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=settings.allowed_methods,
    allow_headers=settings.allowed_headers,
)
app.add_middleware(RequestIDMiddleware)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled errors."""
    logger.error(f'Unhandled exception: {str(exc)}', exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            'error': 'Internal server error',
            'detail': 'An unexpected error occurred.',
            'request_id': getattr(request.state, 'request_id', 'unknown'),
        },
    )


app.include_router(itinerary.router, prefix='/api/v1')


@app.get('/')
async def root():
    """Root endpoint with application information."""
    logger.info('Root endpoint called')
    return {
        'message': 'Welcome to Voyager-T800',
        'service': settings.app_name,
        'version': settings.app_version,
        'description': settings.app_description,
    }


if __name__ == '__main__':
    uvicorn.run('app.main:app', host=settings.host, port=settings.port, reload=settings.debug)
