################################
# PYTHON-BASE
# Shared base with environment settings
################################
FROM python:3.11.9-slim AS python-base

# Python & pip settings
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100
    
# Poetry settings
ENV POETRY_VERSION=2.1.4 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1
    
# Paths
ENV PYSETUP_PATH="/opt/pysetup" \
    VENV_PATH="/opt/pysetup/.venv"

# Unicode support
ENV LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

# Add Poetry and venv to PATH
ENV PATH="$POETRY_HOME/bin:$VENV_PATH/bin:$PATH"


################################
# BUILDER-BASE
# Installs Poetry + dependencies
################################
FROM python-base AS builder-base

# System dependencies for building Python packages
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        curl \
        build-essential \
        libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip to the latest version
RUN pip install --upgrade pip

# Install Poetry with checksum validation
RUN --mount=type=cache,target=/root/.cache \
    curl -sSL https://install.python-poetry.org | python3 -

WORKDIR $PYSETUP_PATH

# Copy dependency files first (cache efficient)
COPY pyproject.toml poetry.lock ./

# Install only production dependencies
# The --mount will mount the buildx cache directory to where 
# Poetry and Pip store their cache so that they can re-use it
RUN --mount=type=cache,target=/root/.cache \
    poetry install --only main --no-root --no-ansi


################################
# DEVELOPMENT IMAGE
################################
FROM python-base AS dev

WORKDIR $PYSETUP_PATH

# Copy Poetry + venv from builder
COPY --from=builder-base $POETRY_HOME $POETRY_HOME
COPY --from=builder-base $PYSETUP_PATH $PYSETUP_PATH

# Install dev dependencies
RUN --mount=type=cache,target=/root/.cache \
    poetry install --with dev --no-root --no-ansi

WORKDIR /app

# Expose dev port

# Hot reload server
CMD uvicorn app.main:app --reload --host ${HOST:-0.0.0.0} --port ${CONTAINER_PORT_DEV:-8000} 


################################
# PRODUCTION IMAGE
################################
FROM python-base AS prod
# Create non-root user
RUN useradd -r -m --no-log-init appuser

# Copy venv from builder with correct ownership
COPY --from=builder-base --chown=appuser:appuser $PYSETUP_PATH $PYSETUP_PATH

# Copy application source with correct ownership
COPY --chown=appuser:appuser app /app/app

WORKDIR /app
USER appuser

# Production server with Gunicorn + Uvicorn workers
CMD gunicorn app.main:app -k uvicorn.workers.UvicornWorker -w ${GUNICORN_WORKERS:-4} -b ${HOST:-0.0.0.0}:${CONTAINER_PORT_PROD:-8001} --access-logfile ${ACCESS_LOG_FILE:-}