import logging
from os import getenv
from dotenv import load_dotenv
from fastapi import FastAPI

from app.config.logger.logger import RequestIDMiddleware, setup_logger
from app.api.auth import router as auth_router


load_dotenv()
setup_logger()
logger = logging.getLogger(__name__)

# Fail fast if required AWS credentials are missing
missing_aws = [v for v in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION") if not getenv(v)]
if missing_aws:
    error_msg = f"Missing required AWS environment variables: {', '.join(missing_aws)}"
    logger.error(error_msg)
    logger.error("Application cannot start without AWS credentials. Please export them in the shell.")
    raise RuntimeError(error_msg)


app = FastAPI()
app.add_middleware(RequestIDMiddleware)


@app.get('/')
async def root():
    logger.info('Root endpoint called')
    return {'message': 'Hello World'}
app.include_router(auth_router)