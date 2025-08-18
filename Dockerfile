################################
# PYTHON-BASE
# Shared base with environment settings
################################
FROM python:3.11-slim AS python-base

# Python & pip settings
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100 \
    # Poetry settings
    POETRY_VERSION=2.1.4 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1 \
    # Paths
    PYSETUP_PATH="/opt/pysetup" \
    VENV_PATH="/opt/pysetup/.venv"

# Add Poetry and venv to PATH
ENV PATH="$POETRY_HOME/bin:$VENV_PATH/bin:$PATH"

################################
# BUILDER-BASE
# Installs Poetry + dependencies
################################
FROM python-base AS builder-base

# System dependencies for building Python packages
RUN apt-get update \
    && apt-get install --no-install-recommends -y curl build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN --mount=type=cache,target=/root/.cache \
    curl -sSL https://install.python-poetry.org | python3 -

WORKDIR $PYSETUP_PATH

# Copy dependency files first (cache efficient)
COPY pyproject.toml poetry.lock ./

# Install only production dependencies
# The --mount will mount the buildx cache directory to where 
# Poetry and Pip store their cache so that they can re-use it
RUN --mount=type=cache,target=/root/.cache \
    poetry install --without dev --no-root --no-ansi

################################
# DEVELOPMENT IMAGE
################################
FROM python-base AS dev

ENV FASTAPI_ENV=development

WORKDIR $PYSETUP_PATH

# Copy Poetry + venv from builder
COPY --from=builder-base $POETRY_HOME $POETRY_HOME
COPY --from=builder-base $PYSETUP_PATH $PYSETUP_PATH

# Install dev dependencies
RUN --mount=type=cache,target=/root/.cache \
    poetry install --without dev --no-root --no-ansi

WORKDIR /app

# Expose dev port
EXPOSE 8000

# Hot reload server
CMD ["uvicorn", "app.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"]

################################
# PRODUCTION IMAGE
################################
FROM python-base AS prod

ENV FASTAPI_ENV=production

# Create non-root user
RUN useradd -m appuser

# Copy venv from builder
COPY --from=builder-base $PYSETUP_PATH $PYSETUP_PATH

# Copy application source
COPY app /app/app

WORKDIR /app

# Set ownership for non-root user
RUN chown -R appuser:appuser /app $PYSETUP_PATH

USER appuser

# Runtime environment variables (override at runtime if needed)
ENV HOST=0.0.0.0 \
    PORT=8000 \
    WORKERS=4 \
    LOG_LEVEL=info

EXPOSE 8000

# Production server with Gunicorn + Uvicorn workers
CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "-w", "4", "-b", "0.0.0.0:8000", "app.main:app"]