import logging
import weaviate
import threading
import time 

from app.services.weaviate.data_models.attraction_models import (
    AttractionWithChunks, AttractionModel, ChunkBase,
    CoordinatesModel, PropertyValidator, SearchResultAttractionModel
)
from weaviate.classes.query import Filter, QueryReference, MetadataQuery
from weaviate.util import generate_uuid5
from weaviate.classes.data import GeoCoordinate
from datetime import datetime
from app.config.logger.logger import setup_logger
from dotenv import load_dotenv

load_dotenv()
setup_logger()
logger = logging.getLogger('app.services.weaviate.attraction_db_manager')

from typing import Any, Dict, List, Optional, Union, Type
from pydantic import BaseModel, field_validator, ValidationError

class WeaviateMetadata(BaseModel):
    distance: Optional[float] = None
    score: Optional[float] = None
    creation_time: Optional[Union[datetime, str]] = None
    last_update_time: Optional[Union[datetime, str]] = None
    certainty: Optional[float] = None
    explain_score: Optional[str] = None
    is_consistent: Optional[str] = None
    rerank_score: Optional[float] = None


class WeaviateObject(BaseModel):
    uuid: Optional[str] = None
    properties: Union[ChunkBase, AttractionModel]
    references: Optional[SearchResultAttractionModel] = None
    vector: Optional[Dict[str, Any]] = None
    metadata: Optional[WeaviateMetadata] = None

    @field_validator("uuid", mode="before")
    def validate_uuid(cls, v):
        return str(v)

class WeaviateQueryResponse(BaseModel):
    objects: List[WeaviateObject]


class AttractionDBManager:
    """
    CRUD manager for Attraction and Chunk data in Weaviate v4.
    Assumes collections 'Attraction' and 'Chunk' exist with appropriate schema.
    """
    def __init__(self, client: weaviate.WeaviateClient,
                 attraction_collection_name="Attraction",
                 chunk_collection_name="AttractionChunk",
                 tag_set_collection_name="TagSet",
                 attraction_reference_prop_name="fromAttraction"):
        
        self.client = client
        self.attraction_collection = client.collections.get(attraction_collection_name)
        self.chunk_collection = client.collections.get(chunk_collection_name)
        self._tag_update_lock = threading.Lock()
        self.tag_set_collection = client.collections.get(tag_set_collection_name)
        self.prop_validator = PropertyValidator(logger=logger)
        
        self.chunk_collection_name = chunk_collection_name

        chunk_config = self.chunk_collection.config.get()
        reference_names = [ref.name for ref in getattr(chunk_config, "references", [])]
        if attraction_reference_prop_name not in reference_names:
            raise ValidationError(f"Reference property {attraction_reference_prop_name} not found in schema.")
        
        self.attraction_reference_prop_name = attraction_reference_prop_name

    def _ensure_coordinates_model(self, props: dict, coord_key: str = "coordinates"):
        """Ensure coordinates is a CoordinatesModel instance (recreate from existing GeoCoordinate object)."""
        if coord_key not in props:
            return
        c = props[coord_key]

        if not isinstance(c, GeoCoordinate):
            logger.error("Failed to coerce coordinates to CoordinatesModel, unsupported input type: %s", c)
            return

        lon = getattr(c, "longitude", None)
        lat = getattr(c, "latitude", None)
        props[coord_key] = CoordinatesModel(longitude=lon, latitude=lat)

    def _parse_properties_to_model(self, props: dict, model_cls: Optional[Type[BaseModel]]):
        """
        Try to parse `props` into the provided pydantic model class. On validation error,
        logs the exception and returns raw props as fallback (same behaviour as before).
        """
        if not model_cls:
            return props
        try:
            return model_cls(**props)
        except ValidationError as ve:
            logger.error("Failed to parse %s from Weaviate properties: %s", model_cls.__name__, ve)
            return props

    def _metadata_from_obj(self, o) -> Optional[WeaviateMetadata]:
        if not getattr(o, "metadata", None):
            return None
        md = getattr(o, "metadata")
        try:
            return WeaviateMetadata(**md.__dict__)
        except Exception:
            logger.error("Unable to convert metadata to WeaviateMetadata: %s", md)
            return None

    def _build_return_references(self, return_attraction_properties: Optional[List[str]]):
        """
        Validate and build QueryReference list (or None) for returning attraction properties
        attached by reference link.
        """
        if not return_attraction_properties:
            return None

        reference_name = self.attraction_reference_prop_name
        invalid = self.prop_validator.validate_attraction_properties(return_attraction_properties)
        if invalid:
            logger.error(f"Invalid attraction properties in search: {invalid}")
            return_attraction_properties = [p for p in return_attraction_properties if p not in invalid]
            if not return_attraction_properties:
                return None

        return [
            QueryReference(
                link_on=reference_name,
                return_properties=return_attraction_properties
            )
        ]

    def _objects_from_response(
        self,
        response,
        properties_model_cls: Optional[Type[BaseModel]] = None,
        properties_postprocess: Optional[callable] = None,
    ) -> List[WeaviateObject]:
        """
        Convert a weaviate response (with .objects) into a list of WeaviateObject instances.
        properties_model_cls: Pydantic model class to try to construct from each object's properties
        properties_postprocess: optional callable(props_dict) that will be run before model construction
        """
        objs = []
        for o in getattr(response, "objects", []) or []:
            raw_props = o.properties or {}
            # allow coords coercion
            if properties_postprocess:
                try:
                    properties_postprocess(raw_props)
                except Exception as ex:
                    logger.error("Error in properties_postprocess: %s", ex)

            parsed_props = None
            if properties_model_cls:
                parsed_props = self._parse_properties_to_model(raw_props, properties_model_cls)
            else:
                parsed_props = raw_props

            # references: try to unpack into SearchResultAttractionModel when present
            if getattr(o, "references", None) is not None:
                references_parsed = self._unpack_references(getattr(o, "references", None), chunk_uuid=getattr(o, "uuid"))
            else:
                references_parsed = None
                
            metadata_obj = self._metadata_from_obj(o)

            # construct WeaviateObject exactly as before
            objs.append(
                WeaviateObject(
                    uuid=str(getattr(o, "uuid", None)),
                    properties=parsed_props,
                    references=references_parsed,
                    vector=getattr(o, "vector", None),
                    metadata=metadata_obj
                )
            )
        return objs
    
    def _verify_chunk_references(self, chunk_uuids, expected_attraction_uuid, reference_name):
        """
        For each chunk UUID, verify that the attraction reference points to the expected attraction UUID.
        Returns True if all references are correct, False otherwise.
        """
        all_correct = True
        for chunk_uuid in chunk_uuids:
            try:
                obj = self.chunk_collection.query.fetch_object_by_id(
                    uuid=chunk_uuid,
                    return_references=QueryReference(
                        link_on=reference_name
                    )
                )
                refs = obj.references.get(reference_name) if obj.references else None
                if not refs or not refs.objects:
                    logger.error(f"Chunk {chunk_uuid} has no {reference_name} reference.")
                    all_correct = False
                    continue
                ref_obj = refs.objects[0]
                if str(ref_obj.uuid) != str(expected_attraction_uuid):
                    logger.error(
                        f"Chunk {chunk_uuid} {reference_name} reference points to {ref_obj.uuid}, "
                        f"expected {expected_attraction_uuid}"
                    )
                    all_correct = False
                else:
                    logger.debug(f"Chunk {chunk_uuid} correctly references attraction {expected_attraction_uuid}")
            except Exception as e:
                logger.error(f"Error verifying reference for chunk {chunk_uuid}: {e}")
                all_correct = False
        return all_correct

    def _add_references(self, references_to_add, batch_size=100, max_retries=3, retry_base_constant=2):
        """
        Add references between objects in batch mode with verification and retries.
        """
        if not references_to_add:
            logger.info("No references to add")
            return
        
        # Group references by attraction for verification
        refs_by_attraction = {}
        for ref in references_to_add:
            attraction_uuid = ref["to"]
            if attraction_uuid not in refs_by_attraction:
                refs_by_attraction[attraction_uuid] = []
            refs_by_attraction[attraction_uuid].append(ref["from_uuid"])
        
        retry_count = 0
        failed_refs_to_retry = references_to_add
        
        while retry_count < max_retries and failed_refs_to_retry:
            logger.info(f"Adding {len(failed_refs_to_retry)} references (attempt {retry_count + 1}/{max_retries})")
            
            with self.client.batch.fixed_size(batch_size=batch_size) as batch:
                for ref in failed_refs_to_retry:
                    try:
                        batch.add_reference(
                            from_collection=ref["from_collection_name"],
                            from_uuid=ref["from_uuid"],
                            from_property=ref["from_property"],
                            to=ref["to"]
                        )
                    except Exception as e:
                        logger.error(f"Error adding reference from {ref['from_uuid']} to {ref['to']}: {e}")
            
            # Check for failed references after batch completion
            failed_refs = self.chunk_collection.batch.failed_references
            if failed_refs:
                logger.error(f"Failed to add {len(failed_refs)} references in batch")
                for failed_ref in failed_refs:
                    logger.error(f"Failed reference: {failed_ref}")
            
            # Verify all references were created correctly
            all_verified = True
            failed_verifications = []
            
            for attraction_uuid, chunk_uuids in refs_by_attraction.items():
                if not self._verify_chunk_references(chunk_uuids, attraction_uuid, self.attraction_reference_prop_name):
                    all_verified = False
                    # Collect failed references for retry
                    for chunk_uuid in chunk_uuids:
                        for ref in references_to_add:
                            if ref["from_uuid"] == chunk_uuid and ref["to"] == attraction_uuid:
                                failed_verifications.append(ref)
                                break
            
            if all_verified:
                logger.info("All references verified successfully")
                return
            
            # Prepare for retry with only failed references
            failed_refs_to_retry = failed_verifications
            retry_count += 1
            
            if retry_count < max_retries:
                logger.warning(f"Reference verification failed for {len(failed_refs_to_retry)} references, retrying...")
                time.sleep(retry_base_constant ** retry_count)  # Add exponential backoff
            else:
                logger.error(f"Failed to add and verify {len(failed_refs_to_retry)} references: {failed_refs_to_retry} after {max_retries} attempts")

    def _prepare_objects(self, items: list[AttractionWithChunks]):
        objects_to_add = []
        references_to_add = []
        results = []
        skipped = []
        unique_batch_tags = set()

        for idx, item in enumerate(items):
            if not item.attraction:
                logger.warning(f"Item №{idx} has no attraction, skipping.")
                skipped.append(idx)
                continue

            attraction_props = item.attraction.to_weaviate_properties()
            unique_batch_tags.update(attraction_props["tags"])
            attraction_uuid = generate_uuid5(attraction_props)
            objects_to_add.append({
                "collection": self.attraction_collection,
                "properties": attraction_props,
                "uuid": attraction_uuid
            })

            chunk_uuids = []

            if not item.chunks:
                logger.warning(f"Attraction {attraction_uuid} has no chunks and will be inserted without them.")
                results.append({
                    "attraction_uuid": attraction_uuid,
                    "chunk_uuids": [],
                    "chunks_present": False
                })
            else:
                for chunk in item.chunks:
                    chunk_props = chunk.to_weaviate_properties()
                    chunk_uuid = generate_uuid5(chunk_props)
                    chunk_uuids.append(chunk_uuid)
                    objects_to_add.append({
                        "collection": self.chunk_collection,
                        "properties": chunk_props,
                        "uuid": chunk_uuid,
                        "vector": chunk.embedding
                    })
                    references_to_add.append({
                        "from_collection_name": self.chunk_collection_name,
                        "from_uuid": chunk_uuid,
                        "from_property": self.attraction_reference_prop_name,
                        "to": attraction_uuid
                    })
                    
            results.append({
                "attraction_uuid": attraction_uuid,
                "chunk_uuids": chunk_uuids,
                "chunks_present": len(chunk_uuids) > 0
            })

        return objects_to_add, references_to_add, results, skipped, list(unique_batch_tags)
    
    def _insert_objects(self, objects_to_add, batch_size, max_batch_errors):
        with self.client.batch.fixed_size(batch_size=batch_size) as batch:
            for obj in objects_to_add:
                try:
                    batch.add_object(
                        collection=obj["collection"].name,
                        properties=obj["properties"],
                        uuid=obj["uuid"],
                        vector=obj.get("vector"),
                    )
                except Exception as e:
                    logger.error(f"Error adding object {obj['uuid']}: {e}")
            if batch.number_errors > max_batch_errors:
                raise Exception("Too many errors during batch import, aborting.")


    def _handle_batch_errors(self):
        failed = self.attraction_collection.batch.failed_objects
        if failed:
            logger.error(f"Number of failed imports: {len(failed)}")
            for i, error_obj in enumerate(failed, 1):
                logger.error(f"Failed object {i}: {error_obj}")

    def _unpack_references(self, refs, chunk_uuid=None):
        """
        Convert references returned by weaviate into SearchResultAttractionModel when possible.
        """
        if not refs:
            return None

        # The existing logic expects a dict of reference lists keyed by property
        reference_name = self.attraction_reference_prop_name
        for k, v in refs.items():
            if k != reference_name:
                logger.error(f"Unknown type of reference in returned from search: {k}")
                continue
            else:
                ref_obj, attraction_props, attraction_uuid = None, None, None
                if len(v.objects) != 1:
                    obj = self.chunk_collection.query.fetch_object_by_id(
                        uuid=chunk_uuid,
                        return_references=QueryReference(link_on=reference_name)
                    )
                    retry_refs = obj.references.get(reference_name) if obj.references else None
                    if not retry_refs.objects or len(retry_refs.objects) != 1:
                        logger.error(f"Chunk {chunk_uuid} has {len(v.objects)} references in property {reference_name}: {v.objects}")
                        return None
                    
                    ref_obj = retry_refs.objects[0]
                    attraction_props = ref_obj.properties or {}
                    attraction_uuid = str(ref_obj.uuid)
                else:   
                    ref_obj = v.objects[0]
                    attraction_props = ref_obj.properties or {}
                    attraction_uuid = str(ref_obj.uuid)

                attraction_props = dict(ref_obj.properties or {})
                self._ensure_coordinates_model(attraction_props, "coordinates")

                try:
                    return SearchResultAttractionModel(**attraction_props)
                except ValidationError as ve:
                    logger.error(
                        "Failed to parse SearchResultAttractionModel from Weaviate properties (uuid=%s): %s",
                        attraction_uuid, ve
                    )
                    return attraction_props
                
    def _insert_unique_tags(self, unique_batch_tags):
        with self._tag_update_lock:
            response = self.tag_set_collection.query.fetch_objects(limit=1)
            if response.objects:
                tagset_obj = response.objects[0]
                existing_tags = set(tagset_obj.properties.get("tags", []))
                merged_tags = list(existing_tags.union(set(unique_batch_tags)))
                self.tag_set_collection.data.update(
                    uuid=tagset_obj.uuid,
                    properties={"tags": merged_tags}
                )
            else:
                self.tag_set_collection.data.insert(
                    properties={"tags": list(unique_batch_tags)}
                )

    def get_unique_tags(self, tag_set_collection_name="TagSet"):
        response = self.tag_set_collection.query.fetch_objects(limit=1)
        if response.objects:
            tagset_obj = response.objects[0]
            existing_tags = tagset_obj.properties.get("tags", [])
            if len(existing_tags) == 0:
                logging.error(f"Got and empty list of tags for object {tagset_obj}")
            return existing_tags
        else:
            logging.error(f"Got no objects in {tag_set_collection_name} collection response: {response}") 

    def batch_insert_attractions_with_chunks(
            self,
            items: list[AttractionWithChunks],
            batch_size=100,
            max_batch_errors=10,
            wait_for_indexing=True
    ):
        """
        Batch insert a list of AttractionWithChunks objects and their chunks, with references.
        Returns a dict with keys:
            "results": list of dicts with attraction_uuid and chunk_uuids, chunks_present flag for each item.
            "skipped": list of indexes of skipped items.
        """
        objects_to_add, references_to_add, results, skipped, unique_batch_tags = self._prepare_objects(items)
        self._insert_objects(objects_to_add, batch_size, max_batch_errors)
        if wait_for_indexing:
            self.chunk_collection.batch.wait_for_vector_indexing()
            self.attraction_collection.batch.wait_for_vector_indexing()
        self._add_references(references_to_add)

        if unique_batch_tags:
            self._insert_unique_tags(unique_batch_tags)

        self._handle_batch_errors()
        return {"results": results, "skipped": skipped}

    def get_attraction(self, uuid: str) -> Optional[dict]:
        """
        Fetch an attraction by UUID.
        """
        obj = self.attraction_collection.query.fetch_object_by_id(uuid)
        return obj.properties if obj else None

    def get_chunks_by_attraction(self, attraction_uuid: str) -> List[dict]:
        """
        Fetch all chunks linked to a given attraction via the attraction reference.
        """
        reference_name = self.attraction_reference_prop_name
        response = self.chunk_collection.query.fetch_objects(
            filters=Filter.by_ref(reference_name).by_id().equal(attraction_uuid),
            limit=1000
        )
        return [obj.properties for obj in response.objects]

    def update_attraction(self, uuid: str, new_data: dict):
        """
        Update an attraction object by UUID.
        Only specified properties will be updated.
        """
        try:
            self.attraction_collection.data.update(uuid=uuid, properties=new_data)
        except Exception as e:
            logger.error(f"Failed to update attraction {uuid}: {e}")

    def replace_attraction(self, uuid: str, new_data: dict):
        """
        Replace an entire attraction object by UUID.
        All unspecified properties will be deleted.
        """
        try:
            self.attraction_collection.data.replace(uuid=uuid, properties=new_data)
        except Exception as e:
            logger.error(f"Failed to replace attraction {uuid}: {e}")

    def delete_attraction(self, uuid: str):
        """
        Delete an attraction and all its linked chunks by UUID.
        """
        reference_name = self.attraction_reference_prop_name
        try:
            self.chunk_collection.data.delete_many(
                where=Filter.by_ref(reference_name).by_id().equal(uuid)
            )
            self.attraction_collection.data.delete_by_id(uuid)
        except Exception as e:
            logger.error(f"Failed to delete attraction {uuid} and its chunks: {e}")

    def delete_chunk(self, uuid: str):
        """
        Delete a chunk by UUID.
        """
        try:
            self.chunk_collection.data.delete_by_id(uuid)
        except Exception as e:
            logger.error(f"Failed to delete chunk {uuid}: {e}")

    def vector_search_chunks(
        self,
        query_vector: list,
        limit: int = 10,
        filters: Optional[Filter] = None,
        return_metadata: Optional[MetadataQuery] = None,
        return_attraction_properties: Optional[list[str]] = None
    ) -> WeaviateQueryResponse:
        """
        Vector search for chunks using a query vector.
        """
        return_references = self._build_return_references(return_attraction_properties)

        response = self.chunk_collection.query.near_vector(
            near_vector=query_vector,
            limit=limit,
            filters=filters,
            return_metadata=return_metadata,
            return_references=return_references
        )

        # ChunkBase is the model we want for chunk properties
        objects = self._objects_from_response(
            response,
            properties_model_cls=ChunkBase,
        )
        return WeaviateQueryResponse(objects=objects)

    def keyword_search_chunks(
        self,
        query: str,
        query_properties: List[str] = ["name^2", "city^2", "chunk_text"],
        limit: int = 10,
        filters: Optional[Filter] = None,
        return_metadata: Optional[MetadataQuery] = None,
        return_attraction_properties: Optional[list[str]] = None
    ) -> WeaviateQueryResponse:
        """
        Keyword (BM25) search for chunks using a query string.
        """
        return_references = self._build_return_references(return_attraction_properties)

        if query_properties:
            invalid = self.prop_validator.validate_chunk_query_properties(query_properties)
            if invalid:
                logger.error(f"Invalid attraction properties in keyword search: {invalid}")
                query_properties = [p for p in query_properties if p not in invalid]

        response = self.chunk_collection.query.bm25(
            query=query,
            query_properties=query_properties,
            limit=limit,
            filters=filters,
            return_metadata=return_metadata or MetadataQuery(score=True),
            return_references=return_references
        )
        objects = self._objects_from_response(
            response,
            properties_model_cls=ChunkBase,
        )
        return WeaviateQueryResponse(objects=objects)

    def hybrid_search_chunks(
        self,
        query: str,
        vector: List[float],
        query_properties: List[str] = ["name^2", "city^2", "tags"],
        limit: int = 10,
        filters: Optional[Filter] = None,
        alpha: float = 0.75,
        return_metadata: Optional[MetadataQuery] = None,
        return_attraction_properties: Optional[list[str]] = None
    ) -> WeaviateQueryResponse:
        """
        Hybrid search for chunks using a query string (combines vector and keyword search).
        """
        return_references = self._build_return_references(return_attraction_properties)

        if query_properties:
            invalid = self.prop_validator.validate_chunk_query_properties(query_properties)
            if invalid:
                logger.error(f"Invalid attraction properties in hybrid search: {invalid}")
                query_properties = [p for p in query_properties if p not in invalid]

        response = self.chunk_collection.query.hybrid(
            query=query,
            vector=vector,
            query_properties=query_properties,
            limit=limit,
            filters=filters,
            alpha=alpha,
            return_metadata=return_metadata or MetadataQuery(score=True),
            return_references=return_references
        )

        objects = self._objects_from_response(
            response,
            properties_model_cls=ChunkBase,
        )
        return WeaviateQueryResponse(objects=objects)

    def filter_attractions(
        self,
        filters: Filter,
        limit: int = 10,
        return_metadata: Optional[MetadataQuery] = None
    ) -> WeaviateQueryResponse:
        """
        Filter attractions using Weaviate filters.
        """
        response = self.attraction_collection.query.fetch_objects(
            filters=filters,
            limit=limit,
            return_metadata=return_metadata
        )

        def postprocess(p):
            self._ensure_coordinates_model(p, "coordinates")

        objects = self._objects_from_response(
            response,
            properties_model_cls=AttractionModel,  # we will run custom parsing below for attractions
            properties_postprocess=postprocess
        )

        return WeaviateQueryResponse(objects=objects)

    def keyword_search_attractions(
        self,
        query: str,
        query_properties: List[str] = ["name^2", "city^2", "address"],
        limit: int = 10,
        filters: Optional[Filter] = None,
        return_metadata: Optional[MetadataQuery] = None
    ) -> WeaviateQueryResponse:
        """
        Keyword (BM25) search for attractions using a query string.
        """
        if query_properties:
            invalid = self.prop_validator.validate_attraction_query_properties(query_properties)
            if invalid:
                logger.error(f"Invalid attraction properties in attraction keyword search: {invalid}")
                query_properties = [p for p in query_properties if p not in invalid]

        response = self.attraction_collection.query.bm25(
            query=query,
            query_properties=query_properties,
            limit=limit,
            filters=filters,
            return_metadata=return_metadata or MetadataQuery(score=True)
        )

        # same postprocess for attractions
        def postprocess(p):
            self._ensure_coordinates_model(p, "coordinates")

        objects = self._objects_from_response(response, properties_model_cls=AttractionModel, properties_postprocess=postprocess)

        return WeaviateQueryResponse(objects=objects)
