import pytest
from app.services.weaviate.schema_manager import SchemaManager
from app.services.weaviate.data_models.schema_models import SchemaConfigModel, Property
from app.services.weaviate.weaviate_client import load_config_from_yaml

CONNECTION_CONFIG = load_config_from_yaml("app/config/weaviate_connection.yaml")

@pytest.fixture
def schema_manager(client_wrapper):
    return SchemaManager(client_wrapper.client)

@pytest.fixture
def simple_schema():
    return SchemaConfigModel(**{
            "class": "TestCollection",
            "description": "A test collection",
            "properties": [
                Property(name="title", dataType=["text"]),
                Property(name="year", dataType=["int"])
            ],
            "vectorizer": "none",
            "invertedIndexConfig": None,
            "vectorIndexType": "dynamic",
            "vectorIndexConfig": {
                "distance": "cosine"
            }
        }
    )


def test_create_and_get_collection(schema_manager, simple_schema):
    # Clean up before test
    try:
        schema_manager.delete_collection(simple_schema.name)
    except Exception:
        pass

    # Create collection
    schema_manager.create_collection(simple_schema)
    # Get collection and check properties
    collection = schema_manager.get_collection(simple_schema.name)
    config = collection.config.get()
    assert config.name == simple_schema.name
    assert any(p.name == "title" for p in config.properties)
    assert any(p.name == "year" for p in config.properties)
    
def test_update_collection_description(schema_manager, simple_schema):
    try:
        schema_manager.delete_collection(simple_schema.name)
    except Exception:
        pass
    # Ensure collection exists
    schema_manager.create_collection(simple_schema)
    # Update description
    updated_schema = simple_schema.copy(update={"description": "Updated description"})
    schema_manager.update_collection(updated_schema)
    collection = schema_manager.get_collection(simple_schema.name)
    assert collection.config.get().description == "Updated description"

def test_list_collections(schema_manager, simple_schema):
    try:
        schema_manager.delete_collection(simple_schema.name)
    except Exception:
        pass
    schema_manager.create_collection(simple_schema)
    collections = schema_manager.list_collections()
    assert any(name == simple_schema.name for name in collections.keys())

def test_delete_collection(schema_manager, simple_schema):
    try:
        schema_manager.delete_collection(simple_schema.name)
    except Exception:
        pass
    schema_manager.create_collection(simple_schema)
    schema_manager.delete_collection(simple_schema.name)
    collections = schema_manager.list_collections()
    assert not any(c["name"] == simple_schema.name for c in collections)