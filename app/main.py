import logging
from os import getenv
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI

from app.config.logger.logger import RequestIDMiddleware, setup_logger
from app.config.loader import ConfigLoader


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
logger = logging.getLogger(__name__)
config_loader = ConfigLoader(project_root=Path(__file__).resolve().parents[1])
settings = config_loader.get_settings()
model = settings.model.openai.model_name


@app.get('/')
async def root():
    logger.info('Root endpoint called')
    return {'message': 'Hello World', 'model': model}
