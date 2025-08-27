import weaviate
from typing import List, Optional, Dict, Any
from dataclasses import asdict
from app.services.weaviate.dataloader import AttractionWithChunks, ChunkData  # Your dataclasses
from app.services.weaviate.data_models.attraction_models import AttractionModel, EmbeddingModel, EmbeddingMetadataModel  # Your Pydantic models
import logging
from weaviate.collections.classes.data import DataObject
from weaviate.classes.query import Filter
from weaviate.classes.query import MetadataQuery

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

    def create_attraction(self, attraction: AttractionModel) -> str:
        """
        Insert a new attraction object.
        Returns the UUID of the created object.
        """
        # Get the data dict
        data = attraction.export_for_weaviate()
        
        uuid = self.attraction_collection.data.insert(properties=data)
        return uuid

    def create_chunks(self, chunks: List[ChunkData], attraction_uuid: Optional[str] = None) -> List[str]:
        """
        Batch insert chunk objects with proper vector embedding and cross-reference to attraction.
        
        Args:
            chunks: List of ChunkData objects with embedding vectors and denormalized metadata
            attraction_uuid: UUID of the parent attraction to create cross-reference
            
        Returns:
            List of UUIDs for created chunk objects
        """
        if not chunks:
            return []
        
        # Prepare batch insert data
        chunk_objects = []
        
        for chunk in chunks:
            # Get the properties dict from chunk (includes denormalized attraction metadata)        
            chunk_obj = DataObject(
                properties=chunk.to_weaviate_properties(),
                vector=chunk.embedding,
                references={"fromAttraction": attraction_uuid} if attraction_uuid else None
            )
            chunk_objects.append(chunk_obj)
        
        try:
            # Batch insert with vectors and references
            logger.info(f"chunk objects:: {chunk_objects}")
            response = self.chunk_collection.data.insert_many(chunk_objects)
            # Handle response - in Weaviate v4, insert_many returns different formats
            if hasattr(response, 'uuids'):
                uuids = response.uuids
            elif hasattr(response, 'all_responses'):
                uuids = [resp.uuid for resp in response.all_responses if resp.uuid]
            elif isinstance(response, list):
                uuids = [str(uuid) for uuid in response if uuid]
            else:
                # Fallback: try to extract UUIDs from response
                uuids = []
                logger.warning(f"Unexpected response format from chunk insertion: {type(response)}")
            
            logger.info(f"Successfully inserted {len(uuids)} chunks out of {len(chunks)} attempted")
            return uuids
            
        except Exception as e:
            logger.error(f"Failed to insert chunks: {e}")
            raise
    
    def create_attraction_with_chunks(self, attraction_with_chunks: AttractionWithChunks) -> Dict[str, Any]:
        """
        Create an attraction and all its associated chunks in a coordinated operation.
        
        Args:
            attraction_with_chunks: AttractionWithChunks object containing attraction and chunk data
            
        Returns:
            Dict with attraction_uuid and chunk_uuids
        """
        result = {
            "attraction_uuid": None,
            "chunk_uuids": [],
            "success": False
        }
        
        try:
            # First, create the attraction
            if attraction_with_chunks.attraction:
                attraction_uuid = self.create_attraction(attraction_with_chunks.attraction)
                result["attraction_uuid"] = attraction_uuid
                logger.info(f"Created attraction with UUID: {attraction_uuid}")
                
                # Then create chunks with reference to the attraction
                if attraction_with_chunks.chunks:
                    chunk_uuids = self.create_chunks(
                        attraction_with_chunks.chunks, 
                        attraction_uuid
                    )
                    result["chunk_uuids"] = chunk_uuids
                    logger.info(f"Created {len(chunk_uuids)} chunks for attraction {attraction_uuid}")
            else:
                logger.warning(f"No attraction model found for {attraction_with_chunks.source_file}")
                # Still try to insert chunks without attraction reference
                if attraction_with_chunks.chunks:
                    chunk_uuids = self.create_chunks(attraction_with_chunks.chunks)
                    result["chunk_uuids"] = chunk_uuids
            
            result["success"] = True
            return result
            
        except Exception as e:
            logger.error(f"Failed to create attraction with chunks: {e}")
            result["error"] = str(e)
            return result

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
        response = self.chunk_collection.query.near_vector(
            near_vector=query_vector,
            limit=limit,
            filters=filters,
            return_metadata=return_metadata or MetadataQuery(distance=True)
        )
        return [obj.properties for obj in response.objects]

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
        response = self.chunk_collection.query.bm25(
            query=query,
            query_properties=query_properties,
            limit=limit,
            filters=filters,
            return_metadata=return_metadata or MetadataQuery(score=True)
        )
        return [obj.properties for obj in response.objects]
    # See: [Keyword search](https://docs.weaviate.io/weaviate/search/bm25)

    def hybrid_search_chunks(
        self,
        query: str,
        limit: int = 10,
        filters: Optional[Filter] = None,
        alpha: float = 0.75,
        return_metadata: Optional[MetadataQuery] = None
    ) -> List[dict]:
        """
        Hybrid search for chunks using a query string (combines vector and keyword search).
        """
        response = self.chunk_collection.query.hybrid(
            query=query,
            limit=limit,
            filters=filters,
            alpha=alpha,
            return_metadata=return_metadata or MetadataQuery(score=True)
        )
        return [obj.properties for obj in response.objects]
        
    def filter_attractions(
        self,
        filters: Filter,
        limit: int = 10,
        return_metadata: Optional[MetadataQuery] = None
    ) -> List[dict]:
        """
        Filter attractions using Weaviate filters.
        """
        response = self.attraction_collection.query.fetch_objects(
            filters=filters,
            limit=limit,
            return_metadata=return_metadata
        )
        return [obj.properties for obj in response.objects]

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
        response = self.attraction_collection.query.bm25(
            query=query,
            query_properties=query_properties,
            limit=limit,
            filters=filters,
            return_metadata=return_metadata or MetadataQuery(score=True)
        )
        return [obj.properties for obj in response.objects]