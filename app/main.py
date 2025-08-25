import logging

from dotenv import load_dotenv
from fastapi import FastAPI

from app.config.logger.logger import RequestIDMiddleware, setup_logger


load_dotenv()

# Fail fast if required AWS credentials are missing
import os
missing_aws = [v for v in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION") if not os.getenv(v)]
if missing_aws:
    raise RuntimeError(f"Missing required AWS environment variables: {', '.join(missing_aws)}")

setup_logger()

app = FastAPI()
app.add_middleware(RequestIDMiddleware)
logger = logging.getLogger(__name__)


@app.get('/')
async def root():
    logger.info('Root endpoint called')
    return {'message': 'Hello World'}
