# Docker Setup Guide

This guide covers the Docker configuration and setup for Voyager T800, including development and production environments.

## Overview

The project uses Docker Compose to manage multiple services:
- **API Services**: FastAPI application (dev/prod profiles)
- **DynamoDB**: Local DynamoDB instance for development
- **Redis**: Caching layer with authentication
- **Weaviate**: Vector database for embeddings

## Quick Start

### Prerequisites

1. **Install Docker and Docker Compose**
2. **Set up environment files:**
   ```bash
   # Copy example files
   cp .env.example .env
   cp .prod.env.example .prod.env
   
   # Edit with your values
   nano .env
   nano .prod.env
   ```
3. **Set AWS credentials** in your shell environment:
   ```bash
   export AWS_ACCESS_KEY_ID=your-access-key-id
   export AWS_SECRET_ACCESS_KEY=your-secret-access-key
   export AWS_REGION=eu-central-1
   ```

### Quick Setup Checklist

- [ ] Docker and Docker Compose installed
- [ ] `.env` file created with development settings
- [ ] `.prod.env` file created with production settings  
- [ ] AWS credentials exported in shell

### Development Environment

```bash
# Start development stack
docker compose --profile dev up --build

# Stop development stack
docker compose --profile dev down
```

### Production Environment

```bash
# Start production stack
docker compose --profile prod --env-file .prod.env up --build 

# Stop production stack
docker compose --profile prod down
```

## Service Configuration

### API Services

#### Development API (`api-dev`)
- **Profile**: `dev`
- **Port**: 8000 (configurable via `HOST_PORT_DEV`)
- **Features**:
  - Hot reload enabled
  - Mounted source code directories
  - Health checks enabled
- **Volume Mounts**:
  ```yaml
  volumes:
    - ./app/api:/app/app/api
    - ./app/chains:/app/app/chains
    - ./app/config:/app/app/config
    - ./app/frontend:/app/app/frontend
    - ./app/main.py:/app/app/main.py
    - ./app/__init__.py:/app/app/__init__.py
  ```

#### Production API (`api`)
- **Profile**: `prod`
- **Port**: 8001 (configurable via `HOST_PORT_PROD`)
- **Features**:
  - Optimized production build
  - No source code mounting
  - Health checks enabled

### Infrastructure Services

#### DynamoDB Local
- **Container**: `dynamodb-local`
- **Port**: Configurable via `DYNAMO_HOST_PORT`
- **Data Persistence**: `./dynamodb` folder mounted for local access
- **Health Check**: Custom HTTP status check (expects 400 for DynamoDB)

#### Redis
- **Container**: `redis-cache`
- **Port**: Configurable via `REDIS_HOST_PORT`
- **Authentication**: Uses Docker secrets for password
- **Data Persistence**: Named volume for Redis data
- **Health Check**: Redis ping with authentication

#### Weaviate
- **Container**: `weaviate`
- **Ports**: HTTP API and gRPC API
- **Data Persistence**: Named volume for vector data
- **Health Check**: Weaviate readiness endpoint

## Environment Configuration

### Environment Variable Sources

The application uses three different sources for configuration:

#### 1. Shell Environment Variables (REQUIRED)
**These MUST be exported in your shell before running Docker Compose:**

```bash
export AWS_ACCESS_KEY_ID=your-access-key-id
export AWS_SECRET_ACCESS_KEY=your-secret-access-key
export AWS_REGION=eu-central-1
```

**Why shell export?** Security - AWS credentials are never stored in files and are passed directly from your shell to the containers.

#### 2. Environment Files
**`.env` file (Development):**
```bash
# DynamoDB Configuration
DYNAMO_HOST_PORT=8003
DYNAMO_CONTAINER_PORT=8000

# Redis Configuration  
REDIS_HOST_PORT=6379
REDIS_CONTAINER_PORT=6379

# Weaviate Configuration
WEAVIATE_DB_HOST_PORT=8090
WEAVIATE_DB_CONTAINER_PORT=8080
GRPS_API_PORT=50051
PERSISTENCE_DATA_PATH=/var/lib/weaviate

# API Ports
HOST_PORT_DEV=8000
CONTAINER_PORT_DEV=8000
```

**`.prod.env` file (Production):**
```bash
# Same variables as .env but with production values
DYNAMO_HOST_PORT=8003
DYNAMO_CONTAINER_PORT=8003
REDIS_HOST_PORT=6379
REDIS_CONTAINER_PORT=6379
WEAVIATE_DB_HOST_PORT=8090
WEAVIATE_DB_CONTAINER_PORT=8090
GRPS_API_PORT=50051
PERSISTENCE_DATA_PATH=/var/lib/weaviate
HOST_PORT_PROD=8001
CONTAINER_PORT_PROD=8001
```
 

- **`.env`**: Development-specific settings
- **`.prod.env`**: Production-specific settings

### Required Environment Variables

```bash
# DynamoDB
DYNAMO_HOST_PORT=8000
DYNAMO_CONTAINER_PORT=8000

# Redis
REDIS_HOST_PORT=6379
REDIS_CONTAINER_PORT=6379
REDIS_PASSWORD=your_redis_password

# Weaviate
WEAVIATE_DB_HOST_PORT=8080
WEAVIATE_DB_CONTAINER_PORT=8080
GRPS_API_PORT=50051
PERSISTENCE_DATA_PATH=/var/lib/weaviate

# API Ports
HOST_PORT_DEV=8000
CONTAINER_PORT_DEV=8000
HOST_PORT_PROD=8001
CONTAINER_PORT_PROD=8001

## Volume Management

### Named Volumes
- `weaviate_data`: Vector database storage
- `redis_data`: Redis data persistence
- `dynamodb_data`: DynamoDB data storage

### Bind Mounts
- `./dynamodb:/home/dynamodblocal/data`: DynamoDB data persistence
- Source code directories (dev only): For hot reloading

## Health Checks

All services include health checks to ensure proper startup order:

```yaml
depends_on:
  dynamodb-local:
    condition: service_healthy
  redis:
    condition: service_healthy
  weaviate-db:
    condition: service_healthy
```

## Troubleshooting

### Common Issues

1. **Port Conflicts**: Ensure ports aren't already in use
2. **AWS Credentials**: Verify AWS credentials are exported in shell
3. **Volume Permissions**: Check folder permissions for bind mounts
4. **Health Check Failures**: Review service logs for startup issues

### Debugging Commands

```bash
# View service logs
docker compose --profile dev logs api-dev

# Check service status
docker compose --profile dev ps

# Access running container
docker compose --profile dev exec api-dev bash

# View volume contents
docker volume inspect voyager-t800_weaviate_data
```

### Logs and Monitoring

```bash
# Follow logs in real-time
docker compose --profile dev logs -f

# View specific service logs
docker compose --profile dev logs -f api-dev

# Check resource usage
docker stats
```

## Security Considerations

- **AWS Credentials**: Never stored in files, only in shell environment
- **Network Isolation**: Services communicate via internal `app-network`
- **Port Exposure**: Only necessary ports exposed to host

## Performance Optimization

### Development
- Hot reload enabled for fast iteration
- Source code bind mounts for real-time changes

### Production
- Multi-stage Docker builds
- No development tools included
- Optimized health checks
- Minimal volume mounts
