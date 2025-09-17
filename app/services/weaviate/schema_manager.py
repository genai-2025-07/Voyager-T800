import yaml
from pydantic import ValidationError
from typing import Optional, Dict

import weaviate
import weaviate.classes as wvc
from app.services.weaviate.data_models.schema_models import SchemaConfigModel, Property

# TODO: move to centralized config
def parse_weaviate_schema_config(yaml_path: str) -> SchemaConfigModel:
    """
    Parse a Weaviate schema YAML config and return a validated Pydantic object.
    """
    with open(yaml_path, "r") as f:
        raw_config = yaml.safe_load(f)
    try:
        config = SchemaConfigModel.model_validate(raw_config)
    except ValidationError as e:
        raise ValueError(f"Schema validation error: {e}")
    return config


class SchemaManager:
    """
    A schema manager for Weaviate v4 that creates, updates, gets, and deletes collections
    using Pydantic/YAML schema models as input.

    This class maps your Pydantic/YAML schema to Weaviate's config classes.
    """

    def __init__(self, client: weaviate.WeaviateClient):
        """
        Initialize the schema manager with a Weaviate v4 client.

        :param client: An instance of weaviate.WeaviateClient (v4).
        """
        self.client = client

    def _map_data_type(self, data_type: str):
        mapping = {
            "text": wvc.config.DataType.TEXT,
            "text[]": wvc.config.DataType.TEXT_ARRAY,
            "int": wvc.config.DataType.INT,
            "int[]": wvc.config.DataType.INT_ARRAY,
            "number": wvc.config.DataType.NUMBER,
            "number[]": wvc.config.DataType.NUMBER_ARRAY,
            "boolean": wvc.config.DataType.BOOL,
            "boolean[]": wvc.config.DataType.BOOL_ARRAY,
            "date": wvc.config.DataType.DATE,
            "date[]": wvc.config.DataType.DATE_ARRAY,
            "uuid": wvc.config.DataType.UUID,
            "uuid[]": wvc.config.DataType.UUID_ARRAY,
            "blob": wvc.config.DataType.BLOB,
            "object": wvc.config.DataType.OBJECT,
            "object[]": wvc.config.DataType.OBJECT_ARRAY,
            "geoCoordinates": wvc.config.DataType.GEO_COORDINATES,
        }
        # If not a primitive type, assume it's a cross-reference to another collection
        return mapping.get(data_type, data_type)

    def _property_from_model(self, prop_model: Property):
        # If the data type is not primitive, treat as a cross-reference
        if prop_model.dataType[0] not in self._primitive_types():
            # Cross-reference: use ReferenceProperty
            return wvc.config.ReferenceProperty(
                name=prop_model.name,
                target_collection=prop_model.dataType[0],
                description=getattr(prop_model, "description", None)
            )
        else:
            # Primitive type: use Property
            data_types = [self._map_data_type(dt) for dt in prop_model.dataType]
            data_type = data_types[0] if len(data_types) == 1 else data_types

            nested = None
            if getattr(prop_model, "nestedProperties", None):
                nested = [self._property_from_model(np) for np in prop_model.nestedProperties]

            tokenization = getattr(prop_model, "tokenization", None)
            if isinstance(tokenization, str):
                tokenization = wvc.config.Tokenization(tokenization)

            return wvc.config.Property(
                name=prop_model.name,
                data_type=data_type,
                nested_properties=nested,
                tokenization=tokenization
            )
        
    def _primitive_types(self):
        return {
            "text", "text[]", "int", "int[]", "number", "number[]", "boolean", "boolean[]",
            "date", "date[]", "uuid", "uuid[]", "blob", "object", "object[]", "geoCoordinates"
        }

    def create_collection(self, schema_config: SchemaConfigModel):
        """
        Create a collection in Weaviate from a validated Pydantic schema config.

        :param schema_config: A validated SchemaConfigModel instance.
        :return: The created collection object.
        """
        properties = [self._property_from_model(p) for p in schema_config.properties]
        references = [el for el in properties if isinstance(el, wvc.config.ReferenceProperty)]
        properties = [el for el in properties if isinstance(el, wvc.config.Property)]
        # Vectorizer config
        if schema_config.vectorizer == "none":
            vector_config = wvc.config.Configure.Vectors.self_provided()
        else:
            raise ValueError(f"Unsupported vectorizer: {schema_config.vectorizer}")

        # Inverted index config
        inverted_index_config = None
        if schema_config.invertedIndexConfig:
            inverted_index_config = wvc.config.Configure.inverted_index(
                index_timestamps=schema_config.invertedIndexConfig.indexTimestamps,
                index_null_state=schema_config.invertedIndexConfig.indexNullState,
                index_property_length=schema_config.invertedIndexConfig.indexPropertyLength,
            )

        return self.client.collections.create(
            name=schema_config.name,
            description=schema_config.description,
            properties=properties,
            references=references,
            vector_config=vector_config,
            inverted_index_config=inverted_index_config,
        )

    def update_collection(
        self,
        schema_config: SchemaConfigModel,
        *,
        description: Optional[str] = None,
        inverted_index_overrides: Optional[Dict[str, bool]] = None,
    ):
        """
        Update mutable settings of a collection in Weaviate from a validated Pydantic schema config.

        Optional arguments:
          - description: override description to set (defaults to schema_config.description)
          - inverted_index_overrides: dict with keys 'index_timestamps', 'index_null_state', 'index_property_length'
            to override values from schema_config.invertedIndexConfig.
        """
        collection = self.client.collections.get(schema_config.name)

        update_kwargs = {}

        # Description is mutable; prefer explicit arg, then schema_config
        desc_value = description if description is not None else schema_config.description
        if desc_value is not None:
            update_kwargs["description"] = desc_value

        # Inverted index config is mutable; allow overrides via argument
        inv_cfg = None
        if inverted_index_overrides is not None:
            # use explicit overrides (caller can supply partial dict)
            inv_cfg = wvc.config.Reconfigure.inverted_index(
                index_timestamps=bool(inverted_index_overrides.get("index_timestamps", False)),
                index_null_state=bool(inverted_index_overrides.get("index_null_state", False)),
                index_property_length=bool(inverted_index_overrides.get("index_property_length", False)),
            )
        elif schema_config.invertedIndexConfig:
            inv_cfg = wvc.config.Reconfigure.inverted_index(
                index_timestamps=schema_config.invertedIndexConfig.indexTimestamps,
                index_null_state=schema_config.invertedIndexConfig.indexNullState,
                index_property_length=schema_config.invertedIndexConfig.indexPropertyLength,
            )

        if inv_cfg:
            update_kwargs["inverted_index_config"] = inv_cfg

        if not update_kwargs:
            raise ValueError("No mutable fields provided for update.")

        return collection.config.update(**update_kwargs)

    def collection_exists(self, name: str) -> bool:
        """
        Check if collection exists by name
        """
        return self.client.collections.exists(name)

    def get_collection(self, name: str):
        """
        Get a collection object by name.

        :param name: Name of the collection.
        :return: The collection object.
        """
        return self.client.collections.use(name)

    def delete_collection(self, name: str):
        """
        Delete a collection and all its objects.

        :param name: Name of the collection to delete.
        """
        self.client.collections.delete(name)

    def list_collections(self, simple: bool = False):
        """
        List all collections in the Weaviate instance.

        :param simple: If True, returns a simplified list. If False, returns full definitions.
        :return: List of collection definitions.
        """
        return self.client.collections.list_all(simple=simple)