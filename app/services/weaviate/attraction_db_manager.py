import logging
from typing import List, Optional
import weaviate

from app.services.weaviate.data_models.attraction_models import (
    AttractionWithChunks
)
from weaviate.classes.query import Filter
from weaviate.classes.query import MetadataQuery
from weaviate.util import generate_uuid5

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

    def batch_insert_attractions_with_chunks(self, items: list[AttractionWithChunks],
                                             batch_size=100) -> list:
        """
        Batch insert a list of AttractionWithChunks objects and their chunks, with references.
        Returns a list of dicts with attraction_uuid and chunk_uuids for each item.
        """
        results = []

        # Prepare all objects and references
        objects_to_add = []
        references_to_add = []

        for idx, item in enumerate(items):
            if not item.attraction:
                logger.warning(f"Item №{idx} has no attraction, skipping.")
                continue  # Skip if no attraction

            # Generate attraction UUID and properties
            attraction_props = item.attraction.to_weaviate_properties()
            attraction_uuid = generate_uuid5(attraction_props)
            objects_to_add.append({
                "collection": self.attraction_collection,
                "properties": attraction_props,
                "uuid": attraction_uuid
            })

            chunk_uuids = []

            if not item.chunks or item.chunks is None:
                logger.warning(f"Attraction {attraction_uuid} has no chunks and will be inserted without them.")
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

        # Batch insert all objects and references
        with self.client.batch.fixed_size(batch_size=batch_size) as batch:
            for obj in objects_to_add:
                batch.add_object(
                    collection=obj["collection"].name,  # Specify collection name
                    properties=obj["properties"],
                    uuid=obj["uuid"],
                    vector=obj.get("vector"),
                )
            for ref in references_to_add:
                batch.add_reference(
                    from_collection=ref["collection"].name,  # Specify collection name
                    from_uuid=ref["from_uuid"],
                    from_property=ref["from_property"],
                    to=ref["to"]
                )
            if batch.number_errors > 10:
                raise Exception("Too many errors during batch import, aborting.")

        # Optionally, wait for indexing to finish (recommended for tests)
        self.attraction_collection.batch.wait_for_vector_indexing()

        # Handle failed objects if needed
        failed = self.attraction_collection.batch.failed_objects
        if failed:
            logger.error(f"Number of failed imports: {len(failed)}")
            for i, error_obj in enumerate(failed, 1):
                logger.error(f"Failed object {i}: {error_obj}")

        return results

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
        self.attraction_collection.data.update(uuid=uuid, properties=new_data)

    def replace_attraction(self, uuid: str, new_data: dict):
        """
        Replace an entire attraction object by UUID.
        All unspecified properties will be deleted.
        """
        self.attraction_collection.data.replace(uuid=uuid, properties=new_data)

    def delete_attraction(self, uuid: str):
        """
        Delete an attraction by UUID.
        """
        self.attraction_collection.data.delete_by_id(uuid)

    def delete_chunk(self, uuid: str):
        """
        Delete a chunk by UUID.
        """
        self.chunk_collection.data.delete_by_id(uuid)

    def vector_search_chunks(
        self,
        query_vector: list,
        limit: int = 10,
        filters: Optional[Filter] = None,
        return_metadata: Optional[MetadataQuery] = None
    ) -> List[dict]:
        """
        Vector search for chunks using a query vector.
        """
        return self.chunk_collection.query.near_vector(
            near_vector=query_vector,
            limit=limit,
            filters=filters,
            return_metadata=return_metadata or MetadataQuery(distance=True)
        )

    def keyword_search_chunks(
        self,
        query: str,
        query_properties: List[str] = ["name^2", "city^2", "chunk_text"],
        limit: int = 10,
        filters: Optional[Filter] = None,
        return_metadata: Optional[MetadataQuery] = None
    ) -> List[dict]:
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
    ) -> List[dict]:
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
    ) -> List[dict]:
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
    ) -> List[dict]:
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