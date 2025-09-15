import logging
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

from app.services.weaviate.weaviate_client import WeaviateClientWrapper, load_config_from_yaml
from app.services.weaviate.dataloader import DataLoader
from app.services.weaviate.attraction_db_manager import AttractionDBManager
from app.services.weaviate.schema_manager import SchemaManager, parse_weaviate_schema_config

from app.config.logger.logger import setup_logger

setup_logger()
logger = logging.getLogger('app.services.weaviate.test')

CONNECTION_CONFIG = None  # Use settings-based config instead
ATTRACTION_SCHEMA_PATH = "app/config/attraction_class_schema.yaml"
CHUNK_SCHEMA_PATH = "app/config/attraction_chunk_class_schema.yaml"
EMBEDDINGS_DIR_PATH = "data/embeddings"
METADATA_FILE_PATH = "data/attractions_metadata.csv"

class WeaviateDatabaseSetup:
    """
    Manages Weaviate database setup operations including connection,
    schema management, and data population.
    """
    
    def __init__(self,
                 connection_config=CONNECTION_CONFIG,
                 attraction_schema_path=ATTRACTION_SCHEMA_PATH,
                 chunk_schema_path=CHUNK_SCHEMA_PATH,
                 embeddings_dir_path=EMBEDDINGS_DIR_PATH,
                 metadata_file_path=METADATA_FILE_PATH):
        self.connection_config = connection_config
        self.client_wrapper = None
        self.schema_manager = None

        self.attraction_schema_path = Path(attraction_schema_path)
        self.chunk_schema_path = Path(chunk_schema_path)
        self.embeddings_dir = Path(embeddings_dir_path)
        self.metadata_file = Path(metadata_file_path)
        
    def connect_and_verify(self) -> bool:
        """
        Establish connection to Weaviate and verify health.
        
        Returns:
            bool: True if connection successful and healthy, False otherwise
        """
        try:
            self.client_wrapper = WeaviateClientWrapper(self.connection_config)
            self.client_wrapper.connect()
            
            health = self.client_wrapper.health_check()
            if not health:
                logger.error("Weaviate health check failed; not ready.")
                return False
                
            logger.info("Connected to Weaviate successfully!")
            self.schema_manager = SchemaManager(self.client_wrapper.client)
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to Weaviate: {e}")
            return False
    
    def setup_schemas(self) -> bool:
        """
        Set up required schemas (collections) in Weaviate.
        
        Returns:
            bool: True if all schemas created successfully, False otherwise
        """
        if not self.schema_manager:
            logger.error("No schema manager available. Connect first.")
            return False
            
        # Setup Attraction schema
        if not self._setup_attraction_schema():
            return False
            
        if not self._setup_chunk_schema():
            return False
        
        return True
    
    def _setup_attraction_schema(self) -> bool:
        """Setup the main Attraction schema."""
        try:
            attraction_schema = parse_weaviate_schema_config(str(self.attraction_schema_path))        
            try:
                existing_collection = self.schema_manager.get_collection(attraction_schema.name)
                logger.info(f"Attraction collection already exists: {existing_collection}")
                return True
            except Exception:
                logger.info("Creating Attraction collection...")
                self.schema_manager.create_collection(attraction_schema)
                logger.info("Attraction collection created successfully!")
                return True
                
        except Exception as e:
            logger.error(f"Failed to create Attraction schema: {e}")
            return False
    
    def _setup_chunk_schema(self) -> bool:
        """Setup the optional Chunk schema."""
        try:
            chunk_schema = parse_weaviate_schema_config(str(self.chunk_schema_path))  
            try:
                existing_collection = self.schema_manager.get_collection(chunk_schema.name)
                logger.info(f"Chunk collection already exists: {existing_collection}")
                return True
            except Exception:
                logger.info("Creating Chunk collection...")
                self.schema_manager.create_collection(chunk_schema)
                logger.info("Chunk collection created successfully!")
                return True
                
        except Exception as e:
            logger.warning(f"Could not create Chunk schema (optional): {e}")
            return False
    
    def populate_database(self) -> Optional[Dict[str, Any]]:
        """
        Load and insert attraction data into the database.
        
        Returns:
            Optional[Dict]: Insertion results if successful, None otherwise
        """
        if not self.client_wrapper:
            logger.error("No client connection available. Connect first.")
            return None
            
        try:
            loader = DataLoader(self.embeddings_dir, self.metadata_file)
            grouped_attractions = loader.load_all()
            
            logger.info(f"Loaded {len(grouped_attractions)} attraction groups")
            
            if not grouped_attractions:
                logger.error("No attraction data loaded; cannot proceed with insertions.")
                return None
            
            # Insert data
            db_manager = AttractionDBManager(self.client_wrapper.client)
            attraction_with_chunks_result = db_manager.batch_insert_attractions_with_chunks(
                grouped_attractions)["results"]
                
            logger.info(f"Inserted Groups: {attraction_with_chunks_result}")
            return {"results": attraction_with_chunks_result, "db_manager": db_manager}
            
        except Exception as e:
            logger.exception(f"Error during database population: {e}")
            return None
    
    def get_db_manager(self) -> Optional[AttractionDBManager]:
        """
        Get a database manager instance for querying operations.
        
        Returns:
            Optional[AttractionDBManager]: Database manager if connection exists
        """
        if not self.client_wrapper:
            logger.error("No client connection available. Connect first.")
            return None
            
        return AttractionDBManager(self.client_wrapper.client)
    
    def disconnect(self):
        """Clean up connections."""
        if self.client_wrapper:
            try:
                self.client_wrapper.close()  # Assuming there's a close method
                logger.info("Disconnected from Weaviate")
            except Exception as e:
                logger.warning(f"Error during disconnect: {e}")


def setup_complete_database() -> Tuple[Optional[AttractionDBManager], Optional[WeaviateClientWrapper], Optional[Dict[str, Any]]]:
    """
    Complete database setup: connect, create schemas, and populate data.
    
    Returns:
        Tuple containing db_manager, client_wrapper, and insertion results
    """
    db_setup = WeaviateDatabaseSetup()
    
    # Connect and verify
    if not db_setup.connect_and_verify():
        return None, None, None
    
    # Setup schemas
    if not db_setup.setup_schemas():
        return None, db_setup.client_wrapper, None
    
    # Populate database
    insertion_result = db_setup.populate_database()["results"]
    db_manager = db_setup.get_db_manager()
    
    return db_manager, db_setup.client_wrapper, insertion_result


def setup_database_connection_only() -> Tuple[Optional[AttractionDBManager], Optional[WeaviateClientWrapper]]:
    """
    Setup database connection and schemas only (no data population).
    Useful for querying existing data.
    
    Returns:
        Tuple containing db_manager and client_wrapper
    """
    db_setup = WeaviateDatabaseSetup()
    
    # Connect and verify
    if not db_setup.connect_and_verify():
        return None, None
    
    # Setup schemas (verify they exist)
    if not db_setup.setup_schemas():
        return None, db_setup.client_wrapper
    
    db_manager = db_setup.get_db_manager()
    return db_manager, db_setup.client_wrapper

