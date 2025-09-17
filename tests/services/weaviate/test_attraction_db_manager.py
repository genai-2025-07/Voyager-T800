import random
import time
from app.services.weaviate.attraction_db_manager import AttractionDBManager
from app.services.weaviate.dataloader import (
    AttractionWithChunks
)
from typing import List
from weaviate.classes.query import MetadataQuery
from weaviate.classes.query import Filter
import threading

VECTOR_LEN = 1536

class TestAttractionDBManagerIntegration:
    """Integration tests for AttractionDBManager using a live, clean Weaviate instance for each test."""

    def test_create_and_retrieve_attraction_end_to_end(
        self, db_manager_with_schema: AttractionDBManager,
        sample_attraction_no_chunks_list: List[AttractionWithChunks] 
    ):
        """
        Test complete CRUD cycle for attractions.
        The 'db_manager_with_schema' fixture ensures the schema is ready.
        """
        # Arrange: The fixture has already set up the db_manager and schema.
        # We just need the sample data.
        attraction = sample_attraction_no_chunks_list[0].attraction
        attraction_no_chunks_list = sample_attraction_no_chunks_list
        db_manager = db_manager_with_schema

        # Act 1: Create the attraction
        batch_insert_attractions_res = db_manager.batch_insert_attractions_with_chunks(attraction_no_chunks_list)
        attraction_uuid = batch_insert_attractions_res["results"][0]["attraction_uuid"]
        # Assert 1: Attraction was created successfully
        assert isinstance(attraction_uuid, str)

        # Act 2: Retrieve the attraction
        retrieved = db_manager.get_attraction(attraction_uuid)
        
        # converting to string representation
        retrieved["last_updated"] = retrieved["last_updated"].isoformat().replace("+00:00", "Z")
        # Note: We convert the Pydantic model to a dict for comparison
        attraction_dict = attraction.model_dump(mode='json')
        
        # deleting coordinates because of precision drop in weaviate
        del attraction_dict["coordinates"]
        del retrieved["coordinates"]
        
        # Assert 2: Retrieved data matches the original
        assert retrieved == attraction_dict

        # Act 3: Update the attraction
        update_data = {"name": "Updated Test Attraction"}
        db_manager.update_attraction(attraction_uuid, update_data)
        
        # Assert 3: The update is reflected
        updated = db_manager.get_attraction(attraction_uuid)
        assert updated is not None
        assert updated["name"] == "Updated Test Attraction"
        
        # Check that other fields are unchanged
        original_dict = attraction.model_dump(mode='json')
        assert updated["city"] == original_dict["city"]

        # Act 4: Delete the attraction
        db_manager.delete_attraction(attraction_uuid)

        # Assert 4: Attraction no longer exists
        deleted = db_manager.get_attraction(attraction_uuid)
        assert deleted is None

    def test_create_attraction_with_chunks_transaction_integrity(
            self, db_manager_with_schema: AttractionDBManager,
            sample_attraction_with_chunks_list):
        """Test that attraction and chunks are created atomically"""
        db_manager = db_manager_with_schema

        # Given: An attraction with chunks
        attraction_with_chunks_list = sample_attraction_with_chunks_list
        attraction_with_chunks = attraction_with_chunks_list[0]
        # When: Creating attraction with chunks
        result = db_manager.batch_insert_attractions_with_chunks(attraction_with_chunks_list)
        attraction_uuid = result["results"][0]["attraction_uuid"]
        
        assert isinstance(attraction_uuid, str)

        # Act 2: Retrieve the attraction
        retrieved_attr = db_manager.get_attraction(attraction_uuid)
        
        # converting to string representation
        retrieved_attr["last_updated"] = retrieved_attr["last_updated"].isoformat().replace("+00:00", "Z")
        # Note: We convert the Pydantic model to a dict for comparison
        attraction_dict = attraction_with_chunks.attraction.model_dump(mode='json')
        
        # deleting coordinates because of precision drop in weaviate
        del attraction_dict["coordinates"]
        del retrieved_attr["coordinates"]
        
        # Assert 2: Retrieved data matches the original
        assert retrieved_attr == attraction_dict
        
        retrived_chunks = db_manager.get_chunks_by_attraction(attraction_uuid)
        chunks = attraction_with_chunks.chunks
        chunk_dicts_list = [chunks[idx].to_weaviate_properties() for idx in range(len(chunks))]
        for idx, retrived_chunk in enumerate(retrived_chunks):
            needed_chunk = [c for c in chunk_dicts_list if c["chunk_text"] == retrived_chunk["chunk_text"]][0]
            assert retrived_chunk == needed_chunk

    def test_create_attraction_with_chunks_partial_failure_handling(
            self,
            sample_attraction_no_chunks_list,
            db_manager_with_schema: AttractionDBManager):
        """Test behavior when chunks creation fails but attraction succeeds"""
        # Given: Valid attraction but invalid chunks
        attraction_no_chunks_list = sample_attraction_no_chunks_list
        db_manager = db_manager_with_schema
        # When: Creating with no chunks
        result = db_manager.batch_insert_attractions_with_chunks(attraction_no_chunks_list)
        attraction_uuid = result["results"][0]["attraction_uuid"]
        chunk_uuids = result["results"][0]["chunk_uuids"]

        # Then: Should still create attraction successfully

        assert attraction_uuid is not None
        assert len(chunk_uuids) == 0
        
    def test_vector_search_chunks_with_real_embeddings(
            self, sample_attraction_with_chunks_list,
            db_manager_with_schema: AttractionDBManager):
        """Test vector search functionality with actual embedding vectors"""
        # Given: Chunks with embeddings are inserted
        db_manager = db_manager_with_schema
        attraction_with_chunks_list = sample_attraction_with_chunks_list
        
        # Waits for indexing
        result = db_manager.batch_insert_attractions_with_chunks(attraction_with_chunks_list)
        
        # When: Performing vector search with similar embedding
        query_chunk = attraction_with_chunks_list[0].chunks[0]
        query_vector = query_chunk.embedding  # Use first chunk's embedding
        results = db_manager.vector_search_chunks(
            query_vector=query_vector,
            limit=5,
            return_metadata=MetadataQuery(distance=True)
        )
        
        # Then: Should return relevant results
        assert len(results.objects) > 0
        assert len(results.objects) <= 5
        
        # First result should be exact match (distance ~0)
        first_result = results.objects[0].properties
        assert first_result.chunk_text == query_chunk.chunk_text 

    def test_hybrid_search_chunks_performance_and_accuracy(
            self, db_manager_with_schema,
            sample_attraction_with_chunks_list):
        """Test hybrid search combining vector and keyword search"""
        # Given: Chunks with varied content are inserted
        attraction_with_chunks_list = sample_attraction_with_chunks_list
        db_manager = db_manager_with_schema
        result = db_manager.batch_insert_attractions_with_chunks(
            attraction_with_chunks_list
        )
                
        # When: Performing hybrid search
        search_query = "museum"  # Assuming some chunks contain "museum"
        start_time = time.time()
        
        hybrid_search_results = db_manager.hybrid_search_chunks(
            query=search_query,
            vector=[random.uniform(-1, 1) for i in range(VECTOR_LEN)],
            limit=10,
            alpha=0.75,  # Favor vector search
            return_metadata=MetadataQuery(score=True)
        )
        hybrid_search_results = hybrid_search_results.objects
        search_duration = time.time() - start_time
        
        # Then: Should return results efficiently
        assert search_duration < 1.0  # Should complete within 2 seconds
        assert isinstance(hybrid_search_results, list)

    def test_keyword_search_attractions(
            self,
            db_manager_with_schema,
            sample_multiple_attraction_with_chunks_list):
        """Test BM25 search with various query patterns and filters"""
        # Given: Multiple attractions with different properties
        attraction_with_chunks_list = sample_multiple_attraction_with_chunks_list

        db_manager = db_manager_with_schema
        result = db_manager.batch_insert_attractions_with_chunks(
            attraction_with_chunks_list
        )
        
        # Test 1: Simple keyword search
        results = db_manager.keyword_search_attractions(
            query="holy",
            limit=5,
            return_metadata=MetadataQuery(score=True)
        )
        results = [obj.properties for obj in results.objects]
        assert results[0].name == attraction_with_chunks_list[0].attraction.name
        
        # Test 2: Multi-word query
        results_multi = db_manager.keyword_search_attractions(
            query="Halytskyi District",
            query_properties=["sublocality_level_1"],
            limit=5
        )
        results_multi = [obj.properties for obj in results_multi.objects]
        assert len(results_multi) == 2
        
        # Test 3: Search with filters
        city_filter = Filter.by_property("address").like("*Kropyvnyts'koho Square*")
        filtered_results = db_manager.keyword_search_attractions(
            query="church",
            filters=city_filter,
            limit=5
        )
        filtered_results = [obj.properties for obj in filtered_results.objects]
        assert filtered_results[0].name == attraction_with_chunks_list[1].attraction.name

    def test_filter_attractions_with_multiple_conditions(self,
            db_manager_with_schema,
            sample_multiple_attraction_with_chunks_list):
        # Given: Multiple attractions with different properties
        attraction_with_chunks_list = sample_multiple_attraction_with_chunks_list

        db_manager = db_manager_with_schema
        result = db_manager.batch_insert_attractions_with_chunks(
            attraction_with_chunks_list
        )
        
        # Test 2: Multiple AND conditions
        complex_filter = Filter.by_property("city").equal("Lviv") & \
                        Filter.by_property("rating").greater_than(4.8)
        
        complex_results = db_manager.filter_attractions(
            complex_filter, 
            limit=10,
            return_metadata=MetadataQuery(score=True)
        )
        complex_results = [obj.properties for obj in complex_results.objects]
        assert complex_results[0].name == attraction_with_chunks_list[0].attraction.name
        

    def test_cross_reference_queries_attraction_to_chunks(
            self,
            db_manager_with_schema,
            sample_multiple_attraction_with_chunks_list
        ):
        """Test querying chunks via attraction references"""
        # Given: Attraction with linked chunks
        attraction_with_chunks_list = sample_multiple_attraction_with_chunks_list

        db_manager = db_manager_with_schema
        result = db_manager.batch_insert_attractions_with_chunks(
            attraction_with_chunks_list
        )
        attraction_uuid = result["results"][0]["attraction_uuid"]

        expected_chunk_count = len(attraction_with_chunks_list[0].chunks)

        linked_chunks = db_manager.get_chunks_by_attraction(attraction_uuid)
        
        # Then: Should retrieve all linked chunks
        assert len(linked_chunks) == expected_chunk_count
        
        # All chunks should have denormalized attraction data
        for chunk in linked_chunks:
            assert chunk["name"] == attraction_with_chunks_list[0].attraction.name
            assert chunk["city"] == attraction_with_chunks_list[0].attraction.city
            assert chunk["place_id"] == attraction_with_chunks_list[0].attraction.place_id
            assert "chunk_text" in chunk


    def test_search_result_metadata_completeness(
            self,
            db_manager_with_schema,
            sample_multiple_attraction_with_chunks_list):
        """Test that search results include proper metadata (scores, distances)"""
        # Given: Chunks are inserted
        db_manager = db_manager_with_schema
        attraction_with_chunks_list = sample_multiple_attraction_with_chunks_list

        result = db_manager.batch_insert_attractions_with_chunks(
            attraction_with_chunks_list
        )
        
        # Test vector search metadata
        vector_results = db_manager.vector_search_chunks(
            query_vector=attraction_with_chunks_list[0].chunks[0].embedding,
            limit=5,
            return_metadata=MetadataQuery(distance=True, certainty=True)
        )
        
        for result in vector_results.objects:
            assert result.metadata
            assert isinstance(result.metadata.distance, (int, float))
            assert 0 <= result.metadata.distance <= 2  # Cosine distance range
        
        # Test keyword search metadata
        keyword_results = db_manager.keyword_search_chunks(
            query="Monastery",
            limit=5,
            return_metadata=MetadataQuery(score=True, explain_score=True)
        )
        
        for result in keyword_results.objects:
            assert result.metadata
            assert isinstance(result.metadata.score, (int, float))
        
        # Test hybrid search metadata
        hybrid_results = db_manager.hybrid_search_chunks(
            query="holy",
            vector=[random.uniform(-1, 1) for i in range(VECTOR_LEN)],
            limit=5,
            return_metadata=MetadataQuery.full()
        )
        
        for result in hybrid_results.objects:
            assert result.metadata
            assert hasattr(result.metadata, "score")

    def test_concurrent_read_write_operations(self,
            db_manager_with_schema,
            sample_multiple_attraction_with_chunks_list):
        """Test thread-safe operations on the database manager"""
        db_manager = db_manager_with_schema
        attraction_with_chunks_list = sample_multiple_attraction_with_chunks_list
               
        results = {}
        exceptions = {}
        
        def create_attraction_worker(thread_id):
            try:
                result = db_manager.batch_insert_attractions_with_chunks(
                attraction_with_chunks_list
                )
            except Exception as e:
                exceptions[f"attraction_{thread_id}"] = e
        
        def search_worker(thread_id):
            try:
                search_results = db_manager.keyword_search_attractions(
                    query="church",
                    limit=10
                )
                results[f"search_{thread_id}"] = search_results
            except Exception as e:
                exceptions[f"search_{thread_id}"] = e
        
        # When: Running concurrent operations
        threads = []
        
        # Create multiple threads for different operations
        for i in range(3):
            threads.append(threading.Thread(target=create_attraction_worker, args=(i,)))
            threads.append(threading.Thread(target=search_worker, args=(i,)))
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join(timeout=10)
        
        # Then: All operations should complete without errors
        assert len(exceptions) == 0, f"Concurrent operations failed: {exceptions}"
        
        # Verify results
        attraction_results = [v for k, v in results.items() if k.startswith("attraction_")]
        search_results = [v for k, v in results.items() if k.startswith("search_")]
                
        # All UUIDs should be unique
        all_attraction_uuids = [uuid for uuid in attraction_results if uuid]
        assert len(all_attraction_uuids) == len(set(all_attraction_uuids))

    def test_get_unique_tags_completeness(
            self,
            db_manager_with_schema,
            sample_multiple_attraction_with_chunks_list):
        
        attraction_with_chunks_list = sample_multiple_attraction_with_chunks_list

        db_manager = db_manager_with_schema
        result = db_manager.batch_insert_attractions_with_chunks(
            attraction_with_chunks_list
        )
        expected_attractions_tags = set()
        for attr_w_chunk in attraction_with_chunks_list:
            expected_attractions_tags.update(attr_w_chunk.attraction.tags)

        retieved_tags = db_manager.get_unique_tags()
        assert list(expected_attractions_tags) == retieved_tags
        
    def test_references_keyword_chunk_search(
        self, db_manager_with_schema: AttractionDBManager,
        sample_all_real_attractions: list[AttractionWithChunks]
    ):
        attractions = sample_all_real_attractions
        manager = db_manager_with_schema

        insert_results = manager.batch_insert_attractions_with_chunks(attractions)["results"]

        attraction_props = list(
            attractions[0].attraction.to_weaviate_properties().keys()
        )

        for attraction_with_chunks in attractions:
            for chunk in attraction_with_chunks.chunks:
                chunk_keyword = " ".join(chunk.chunk_text[:50].split(" ")[:5])

                search_res = manager.keyword_search_chunks(
                    query=chunk_keyword,
                    limit=50,
                    return_metadata=MetadataQuery.full(),
                    return_attraction_properties=attraction_props
                )

                search_objects = search_res.objects
                search_props_list = [obj.properties.model_dump() for obj in search_objects]

                chunk_props = chunk.to_weaviate_properties()
                assert chunk_props in search_props_list

                matched_obj = search_objects[search_props_list.index(chunk_props)]

                orig_attraction_props = attraction_with_chunks.attraction.to_weaviate_properties()
                # in weaviate precision for coords is dropping
                del orig_attraction_props["coordinates"]

                referenced_attraction_props = matched_obj.references.to_weaviate_properties()
                # in weaviate precision for coords is dropping
                del referenced_attraction_props["coordinates"]

                assert orig_attraction_props == referenced_attraction_props

