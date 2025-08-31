from __future__ import annotations
import os
import yaml
from pydantic import BaseModel, Field, ValidationError
from typing import Optional

import weaviate
from weaviate.connect import ConnectionParams


class LocalConnectionParams(BaseModel):
    """
    Connection parameters for Weaviate HTTP and (optional) gRPC.
    All fields are required and described for schema / docs.
    """
    http_host: str = Field(..., description="Hostname or IP for Weaviate HTTP endpoint")
    http_port: int = Field(..., description="Port for Weaviate HTTP endpoint")
    http_secure: bool = Field(..., description="Use HTTPS for the HTTP endpoint if true")
    grpc_host: str = Field(..., description="Hostname or IP for Weaviate gRPC endpoint")
    grpc_port: int = Field(..., description="Port for Weaviate gRPC endpoint")
    grpc_secure: bool = Field(..., description="Use TLS for gRPC if true")

class HealthCheckResponse(BaseModel):
    """
    Simple health-check response model.
    """
    is_ready: bool = Field(..., description="Whether the Weaviate HTTP endpoint reports ready")


def load_config_from_yaml(path: str) -> LocalConnectionParams:
    """Load YAML file and parse into LocalConnectionParams (raises on invalid schema)."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Config file not found: {path}")
    with open(path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    try:
        cfg = LocalConnectionParams(**raw)
    except ValidationError as e:
        # Re-raise with a clearer message
        raise RuntimeError(f"Invalid weaviate config at {path}:\n{e}") from e
    return cfg


class WeaviateClientWrapper:
    def __init__(self, params: Optional[LocalConnectionParams] = None):
        self.params = params or LocalConnectionParams()
        self.client = None

    def connect(self):
        # Use explicit instantiation for full control
        connection_params = ConnectionParams.from_params(
            http_host=self.params.http_host,
            http_port=self.params.http_port,
            http_secure=self.params.http_secure,
            grpc_host=self.params.grpc_host,
            grpc_port=self.params.grpc_port,
            grpc_secure=self.params.grpc_secure,
        )
        self.client = weaviate.WeaviateClient(connection_params=connection_params)
        self.client.connect()  # Required for explicit instantiation

    def disconnect(self):
        if self.client:
            self.client.close()
            self.client = None

    def health_check(self) -> HealthCheckResponse:
        if not self.client:
            raise RuntimeError("Client not connected")
        is_ready = self.client.is_ready()
        return HealthCheckResponse(is_ready=is_ready)

