import yaml
from pydantic import BaseModel, Field, ValidationError
from typing import List, Optional, Dict, Any
# Recursive Pydantic model for nested properties
class NestedProperty(BaseModel):
    name: str
    dataType: List[str]
    nestedProperties: Optional[List["NestedProperty"]] = None
    tokenization: Optional[str] = None

NestedProperty.model_rebuild()

class Property(NestedProperty):
    pass

class VectorIndexConfig(BaseModel):
    distance: str
    dynamic: Optional[Dict[str, Any]] = None

class InvertedIndexConfig(BaseModel):
    indexTimestamps: Optional[bool] = None
    indexNullState: Optional[bool] = None
    indexPropertyLength: Optional[bool] = None

class SchemaConfigModel(BaseModel):
    name: str = Field(..., alias="class")
    description: Optional[str]
    vectorizer: str
    vectorIndexType: Optional[str]
    vectorIndexConfig: Optional[VectorIndexConfig]
    properties: List[Property]
    invertedIndexConfig: Optional[InvertedIndexConfig]

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