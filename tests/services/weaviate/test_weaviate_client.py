import pytest
from app.services.weaviate.weaviate_client import WeaviateClientWrapper, load_config_from_yaml

CONNECTION_CONFIG = load_config_from_yaml("app/config/weaviate_connection.yaml")

def test_health_check(client_wrapper):
    response = client_wrapper.health_check()
    assert response is True


def test_disconnect_and_reconnect():
    wrapper = WeaviateClientWrapper(CONNECTION_CONFIG)
    wrapper.connect()
    wrapper.disconnect()
    wrapper.connect()
    response = wrapper.health_check()
    assert response is True
    wrapper.disconnect()


def test_health_check_without_connect():
    wrapper = WeaviateClientWrapper(CONNECTION_CONFIG)
    with pytest.raises(RuntimeError):
        wrapper.health_check()