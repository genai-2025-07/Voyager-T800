import logging
from typing import List, Optional
import weaviate

from app.services.weaviate.data_models.attraction_models import (
    AttractionWithChunks
)
from weaviate.classes.query import Filter
from weaviate.classes.query import MetadataQuery
from weaviate.util import generate_uuid5
from weaviate.collections.classes.internal import (
    QueryReturn
)
from app.config.logger.logger import setup_logger
from dotenv import load_dotenv

load_dotenv()
setup_logger()
logger = logging.getLogger('app.services.weaviate.attraction_db_manager')


class AttractionDBManager:
    """
    CRUD manager for Attraction and Chunk data in Weaviate v4.
    Assumes collections 'Attraction' and 'Chunk' exist with appropriate schema.
    """
    def __init__(self, client: weaviate.WeaviateClient,
                 attraction_collection_name="Attraction",
                 chunk_collection_name="AttractionChunk"):
        self.client = client
        self.attraction_collection = client.collections.get(attraction_collection_name)
        self.chunk_collection = client.collections.get(chunk_collection_name)

    def _prepare_objects(self, items: list[AttractionWithChunks]):
        objects_to_add = []
        references_to_add = []
        results = []
        skipped = []

        for idx, item in enumerate(items):
            if not item.attraction:
                logger.warning(f"Item №{idx} has no attraction, skipping.")
                skipped.append(idx)
                continue

            attraction_props = item.attraction.to_weaviate_properties()
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
                        "collection": self.chunk_collection,
                        "from_uuid": chunk_uuid,
                        "from_property": "fromAttraction",
                        "to": attraction_uuid
                    })

            results.append({
                "attraction_uuid": attraction_uuid,
                "chunk_uuids": chunk_uuids
            })

        return objects_to_add, references_to_add, results, skipped

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

    def _add_references(self, references_to_add, batch_size=100):
        with self.client.batch.fixed_size(batch_size=batch_size) as batch:
            for ref in references_to_add:
                batch.add_reference(
                    from_collection=ref["collection"].name,
                    from_uuid=ref["from_uuid"],
                    from_property=ref["from_property"],
                    to=ref["to"]
                )

    def _handle_batch_errors(self):
        failed = self.attraction_collection.batch.failed_objects
        if failed:
            logger.error(f"Number of failed imports: {len(failed)}")
            for i, error_obj in enumerate(failed, 1):
                logger.error(f"Failed object {i}: {error_obj}")

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
        objects_to_add, references_to_add, results, skipped = self._prepare_objects(items)
        self._insert_objects(objects_to_add, batch_size, max_batch_errors)
        self._add_references(references_to_add)
        if wait_for_indexing:
            self.attraction_collection.batch.wait_for_vector_indexing()
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
        Fetch all chunks linked to a given attraction via the fromAttraction reference.
        """
        response = self.chunk_collection.query.fetch_objects(
            filters=Filter.by_ref("fromAttraction").by_id().equal(attraction_uuid),
            limit=1000  # Adjust as needed
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
        try:
            # Delete all chunks linked to this attraction
            self.chunk_collection.data.delete_many(
                where=Filter.by_ref("fromAttraction").by_id().equal(uuid)
            )
            # Delete the attraction itself
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
        return_metadata: Optional[MetadataQuery] = None
    ) -> QueryReturn:
        """
        Vector search for chunks using a query vector.
        """
        return self.chunk_collection.query.near_vector(
            near_vector=query_vector,
            limit=limit,
            filters=filters,
            return_metadata=return_metadata or MetadataQuery(distance=True),
        )

    def keyword_search_chunks(
        self,
        query: str,
        query_properties: List[str] = ["name^2", "city^2", "chunk_text"],
        limit: int = 10,
        filters: Optional[Filter] = None,
        return_metadata: Optional[MetadataQuery] = None,
    ) -> QueryReturn:
        """
        Keyword (BM25) search for chunks using a query string.
        """
        return self.chunk_collection.query.bm25(
            query=query,
            query_properties=query_properties,
            limit=limit,
            filters=filters,
            return_metadata=return_metadata or MetadataQuery(score=True)
        )

    def hybrid_search_chunks(
        self,
        query: str,
        vector: List[float],
        query_properties: List[str] = ["name^2", "city^2", "tags"],
        limit: int = 10,
        filters: Optional[Filter] = None,
        alpha: float = 0.75,
        return_metadata: Optional[MetadataQuery] = None
    ) -> QueryReturn:
        """
        Hybrid search for chunks using a query string (combines vector and keyword search).

        """
        return self.chunk_collection.query.hybrid(
            query=query,
            vector=vector,
            query_properties=query_properties,
            limit=limit,
            filters=filters,
            alpha=alpha,
            return_metadata=return_metadata or MetadataQuery(score=True)
        )
        
    def filter_attractions(
        self,
        filters: Filter,
        limit: int = 10,
        return_metadata: Optional[MetadataQuery] = None
    ) -> QueryReturn:
        """
        Filter attractions using Weaviate filters.
        """
        return self.attraction_collection.query.fetch_objects(
            filters=filters,
            limit=limit,
            return_metadata=return_metadata
        )

    def keyword_search_attractions(
        self,
        query: str,
        query_properties: List[str] = ["name^2", "city^2", "address"],
        limit: int = 10,
        filters: Optional[Filter] = None,
        return_metadata: Optional[MetadataQuery] = None
    ) -> QueryReturn:
        """
        Keyword (BM25) search for attractions using a query string.
        """
        return self.attraction_collection.query.bm25(
            query=query,
            query_properties=query_properties,
            limit=limit,
            filters=filters,
            return_metadata=return_metadata or MetadataQuery(score=True)
        )