import logging

from contextlib import asynccontextmanager

import uvicorn

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.auth import router as auth_router
from app.api.routes import images, itinerary
from app.config.config import settings
from app.config.logger.logger import RequestIDMiddleware, setup_logger
from app.data_layer.dynamodb_client import DynamoDBClient
from app.services.image.image_storage_manager import ImageStorageManager
from app.config.config import settings


setup_logger()
logger = logging.getLogger(__name__)

# Global client instances
dynamodb_client = None
weaviate_client_wrapper = None

# Check if we should use local DynamoDB
use_local_dynamodb = settings.use_local_dynamodb

# Only require AWS credentials if not using local DynamoDB
if not use_local_dynamodb:
    missing_aws = []
    if not settings.aws_access_key_id:
        missing_aws.append('AWS_ACCESS_KEY_ID')
    if not settings.aws_secret_access_key:
        missing_aws.append('AWS_SECRET_ACCESS_KEY')

    if missing_aws:
        error_msg = f'Missing required AWS environment variables: {", ".join(missing_aws)}'
        logger.error(error_msg)
        logger.error('Application cannot start without AWS credentials. Please export them in the shell.')
        logger.error('Alternatively, set USE_LOCAL_DYNAMODB=true to use local DynamoDB for development.')
        raise RuntimeError(error_msg)
else:
    logger.info('Using local DynamoDB - AWS credentials not required')


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa ARG001
    """Application lifespan manager for startup and shutdown events."""
    global dynamodb_client, weaviate_client_wrapper

    logger.info('Starting Voyager-T800 application...')

    try:
        app.state.image_storage_manager = ImageStorageManager(
            s3_bucket=settings.s3_thumbnail_bucket,
            s3_region=settings.aws_region,
            url_expiration_seconds=3600,  # 1 hour
            max_thumbnail_size=(400, 400),
            thumbnail_quality=85
        )
    except Exception as e:
        logger.error(f'Failed to initialize ImageStorageManager: {str(e)}')
        raise RuntimeError(f'ImageStorageManager initialization failed: {str(e)}')

    try:
        # Initialize DynamoDB client
        logger.info('Initializing DynamoDB client...')
        dynamodb_client = DynamoDBClient()

        # Test DynamoDB connection
        table_name = dynamodb_client.table_name
        logger.info(f'DynamoDB client initialized successfully. Table: {table_name}')

        app.state.dynamodb_client = dynamodb_client

    except Exception as e:
        logger.error(f'Failed to initialize DynamoDB client: {str(e)}')
        raise RuntimeError(f'DynamoDB initialization failed: {str(e)}')

    server_url = f'http://{settings.host}:{settings.port}'
    logger.info(f'Voyager-T800 is running at {server_url}')

    yield

    logger.info('Shutting down Voyager-T800 application...')

    # Cleanup DynamoDB connection
    if dynamodb_client:
        logger.info('DynamoDB client cleanup completed')
        dynamodb_client = None

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


app.include_router(auth_router)
app.include_router(itinerary.router, prefix='/api/v1')
app.include_router(images.router, prefix='/api/v1')


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
