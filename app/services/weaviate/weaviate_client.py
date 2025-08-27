import weaviate
from weaviate.connect import ConnectionParams
from pydantic import BaseModel
from typing import Optional


# Pydantic model for connection parameters
class LocalConnectionParams(BaseModel):
    http_host: str = "localhost"
    http_port: int = 8080
    http_secure: bool = False
    grpc_host: str = "localhost"
    grpc_port: int = 50051
    grpc_secure: bool = False


# Pydantic model for a sample health check response
class HealthCheckResponse(BaseModel):
    is_ready: bool


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

