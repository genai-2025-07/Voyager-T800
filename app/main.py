import logging

from dotenv import load_dotenv
from fastapi import FastAPI

from app.config.logger.logger import RequestIDMiddleware, setup_logger
from app.config.loader import ConfigLoader


load_dotenv()
setup_logger()

app = FastAPI()
app.add_middleware(RequestIDMiddleware)
logger = logging.getLogger(__name__)
config_loader = ConfigLoader()
settings = config_loader.get_settings()
default_model = settings.model.openai.model_name


@app.get('/')
async def root():
    logger.info('Root endpoint called')
    return {'message': 'Hello World', 'model': default_model}
