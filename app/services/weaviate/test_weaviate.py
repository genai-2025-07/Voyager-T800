
import logging

from weaviate.classes.query import Filter
from weaviate.classes.query import MetadataQuery

from app.config.logger.logger import setup_logger
from app.services.weaviate.weaviate_setup import setup_complete_database


setup_logger()
logger = logging.getLogger('app.services.weaviate.db_setup')

def main():
    """Example usage of the refactored setup."""
    try:
        # For complete setup including data population
        db_manager, client_wrapper, insertion_results = setup_complete_database()
        
        if db_manager and client_wrapper:
            logger.info("Database setup completed successfully!")
            # Use db_manager for queries here
            logger.info(f"Inserted Groups: {insertion_results}")
            for res_group in insertion_results:
                attraction_uuid = res_group["attraction_uuid"]

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

            attraction_filter = Filter.by_property("city").equal("Lviv")
            attraction_filtering_res = db_manager.filter_attractions(filters=attraction_filter, limit=50)
            logger.info(f"Attraction filtering results {attraction_filtering_res}")
            attraction_filter_1 = Filter.by_property("city").equal("Kyiv")
            attraction_filtering_res = db_manager.filter_attractions(filters=attraction_filter_1, limit=50)
            logger.info(f"Attraction filtering results {attraction_filtering_res}")

            keyword = "descent"
            attr_keyword_res = db_manager.keyword_search_attractions(
                query=keyword, limit=50, return_metadata=MetadataQuery.full())
            logger.info(f"Attraction keyword search result results {attr_keyword_res}")
                
            chunks_keyword_res = db_manager.keyword_search_chunks(
                query=keyword, limit=50, return_metadata=MetadataQuery.full(),
                return_attraction_properties=["name", "address", "opening_hours"])
            logger.info(f"chunk keyword search result results {chunks_keyword_res}")

            tag_list = db_manager.get_unique_tags()
            logger.info(f"tag list: {tag_list}")
        else:
            logger.error("Database setup failed!")
            
    except Exception as e:
        logger.exception(f"Error in main: {e}")
    
    finally:
        client_wrapper.disconnect()


if __name__ == "__main__":
    main()

