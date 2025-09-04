from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


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