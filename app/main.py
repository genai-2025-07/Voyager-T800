import logging

from dotenv import load_dotenv
from fastapi import FastAPI

from app.config.logger.logger import RequestIDMiddleware, setup_logger


load_dotenv()
setup_logger()

app = FastAPI()
app.add_middleware(RequestIDMiddleware)
logger = logging.getLogger(__name__)


@app.get('/')
async def root():
    logger.info('Root endpoint called')
    return {'message': 'Hello World'}
