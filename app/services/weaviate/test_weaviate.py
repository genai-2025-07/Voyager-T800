import logging
from pathlib import Path

from app.services.weaviate.weaviate_client import WeaviateClientWrapper
from app.services.weaviate.dataloader import DataLoader
from app.services.weaviate.attraction_db_manager import AttractionDBManager
from app.services.weaviate.schema_manager import SchemaManager
from app.services.weaviate.schema_parser import parse_weaviate_schema_config
from weaviate.classes.query import Filter
from weaviate.classes.query import MetadataQuery

from app.config.logger.logger import setup_logger

from dotenv import load_dotenv

# load environment from same folder as this file (app/services/weaviate/.env)
load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

setup_logger()
logger = logging.getLogger('app.services.weaviate.test')


def main():
    # 2. Connect to Weaviate using our client wrapper
    client_wrapper = WeaviateClientWrapper()
    try:
        client_wrapper.connect()
    except Exception as e:
        logger.error(f"Unable to connect to Weaviate: {e}")
        return

    health = client_wrapper.health_check()
    if not health.is_ready:
        logger.error("Weaviate health check failed; not ready.")
        return

    logger.info("Connected to Weaviate!")

    # 3. CREATE SCHEMAS FIRST
    schema_manager = SchemaManager(client_wrapper.client)
    
    # Parse and create Attraction schema
    try:
        attraction_schema_path = Path("app/config/attraction_class_schema.yaml")
        attraction_schema = parse_weaviate_schema_config(str(attraction_schema_path))
        
        try:
            existing_collection = schema_manager.get_collection(attraction_schema.name)
            logger.info(f"Attraction collection already exists {existing_collection}")
        except Exception:
            logger.info("Creating Attraction collection...")
            schema_manager.create_collection(attraction_schema)
            logger.info("Attraction collection created successfully!")
            
    except Exception as e:
        logger.error(f"Failed to create Attraction schema: {e}")
        return

    # Create the Chunk schema if it exists
    try:
        chunk_schema_path = Path("app/config/attraction_chunk_class_schema.yaml")
        if chunk_schema_path.exists():
            chunk_schema = parse_weaviate_schema_config(str(chunk_schema_path))
            try:
                existing_collection = schema_manager.get_collection(chunk_schema.name)
                logger.info(f"Chunk collection already exists {existing_collection}")
            except Exception:
                logger.info("Creating Chunk collection...")
                schema_manager.create_collection(chunk_schema)
                logger.info("Chunk collection created successfully!")
    except Exception as e:
        logger.warning(f"Could not create Chunk schema (optional): {e}")

    # 4. Load embeddings and metadata from disk
    embeddings_dir = Path("data/embeddings")
    metadata_file = Path("data/attractions_metadata.csv")
    loader = DataLoader(embeddings_dir, metadata_file)
    grouped_attractions = loader.load_all()
    
    logger.info(f"Loaded {len(grouped_attractions)} attraction groups (from embeddings and metadata)")

    if not grouped_attractions:
        logger.error("No attraction data loaded; cannot proceed with insertions.")
        return

    # 5. Use the AttractionDBManager to insert attractions and their chunks.
    db_manager = AttractionDBManager(client_wrapper.client)

    for group in grouped_attractions:
        if group.attraction is None:
            logger.warning(f"Skipping group {group.source_file}: missing attraction metadata.")
            continue

        try:
            attraction_with_chunks_result = db_manager.create_attraction_with_chunks(group)
            attraction_uuid = attraction_with_chunks_result["attraction_uuid"]
            logger.info(f"Inserted Group: {attraction_with_chunks_result}")

            fetched = db_manager.get_attraction(attraction_uuid)
            fetched_chunks = db_manager.get_chunks_by_attraction(attraction_uuid)
            if fetched:
                logger.info(f"Fetched Attraction: {fetched.get('name')} \n {fetched}")
            else:
                logger.warning(f"Unable to fetch attraction with UUID {attraction_uuid}")
            if fetched_chunks:
                logger.info(f"Fetched chunks:  \n {fetched_chunks}")
            else:
                logger.warning(f"Unable to fetch chunks for  attraction with UUID {attraction_uuid}")

        except Exception as insert_e:
            logger.exception(f"Error processing group {group.source_file}: {insert_e}")

    attraction_filter = Filter.by_property("city").equal("Lviv")
    attraction_filtering_res = db_manager.filter_attractions(filters=attraction_filter, limit=50)
    logger.info(f"Attraction filtering results {attraction_filtering_res}")
    logger.info(len(attraction_filtering_res))

    attraction_filter_1 = Filter.by_property("city").equal("Kyiv")
    attraction_filtering_res = db_manager.filter_attractions(filters=attraction_filter_1, limit=50)
    logger.info(f"Attraction filtering results {attraction_filtering_res}")
    logger.info(len(attraction_filtering_res))

    keyword = "descent"
    attr_keyword_res = db_manager.keyword_search_attractions(
        query=keyword, limit=50, return_metadata=MetadataQuery.full())
    logger.info(f"Attraction keyword search result results {attr_keyword_res}")
        
    chunks_keyword_res = db_manager.keyword_search_chunks(
        query=keyword, limit=50, return_metadata=MetadataQuery.full())
    logger.info(f"chunk keyword search result results {chunks_keyword_res}")

    client_wrapper.disconnect()
    logger.info("Disconnected from Weaviate.")

if __name__ == "__main__":
    main()