from langchain_community.vectorstores import Weaviate
import weaviate
from weaviate.embedded import EmbeddedOptions
import logging
import glob
import os
import json

logger = logging.getLogger(__name__)

# Weaviate schema (v3.x API)
class_obj = {
    "class": "Document",
    "vectorizer": "none",  # precomputed vectors
    "properties": [
        {
            "name": "text", 
            "dataType": ["text"]
        },
        {
            "name": "source", 
            "dataType": ["text"]
        },
        {
            "name": "city", 
            "dataType": ["text"]
        },
    ]
}


def setup_weaviate(embeddings):
    """
    Sets up the Weaviate vector store with the specified class schema.
    Initializes the embedded Weaviate instance and creates the class if it does not exist.
    Args:
        embeddings: The embedding model to use with the vector store.
    Returns:
        Weaviate vector store instance.
    """
    try:
        client = weaviate.Client(
            embedded_options=EmbeddedOptions()
        )
        client.schema.delete_all()  # Clear existing schema for fresh setup
        
        # Create schema if not exists
        schema = client.schema.get()
        existing_classes = [c["class"] for c in schema["classes"]]

        if "Document" not in existing_classes:
            client.schema.create_class(class_obj)
            logger.info("Created Weaviate class 'Document'.")

        # LangChain vectorstore wrapper
        vector_store = Weaviate(
            client=client,
            index_name="Document",
            text_key="text",
            embedding=embeddings,
            by_text=False,  # we use precomputed vectors
            attributes=["source", "city"],
        )
        return vector_store

    except Exception as e:
        logger.error(f"Error setting up Weaviate: {e}")
        raise


def create_weaviate_db_with_loaded_documents(embeddings, chunks_dir):
    """
    Adds document chunks to the Weaviate vector store.
    """
    vectorstore = setup_weaviate(embeddings)

    json_files = glob.glob(os.path.join(chunks_dir, "*.json"))
    data = []
    for file_path in json_files:
        try:
            with open(file_path, "r") as f:
                chunk_data = json.load(f)
                data.append(chunk_data)
        except Exception as e:
            logger.error(f"ERROR loading {file_path}: {e}")

    logger.info(f"Loaded {len(data)} document chunks from JSON files.")

    # Add chunks to Weaviate
    if data:
        texts = [d["text"] for d in data]
        vectors = [d["embedding"] for d in data]
        metadatas = [{"source": d["metadata"]["source_file"], "city": d["metadata"]["city"]} for d in data]
        try:
            vectorstore.add_texts(texts=texts, metadatas=metadatas, vectors=vectors)
            logger.info("Successfully loaded document chunks into Weaviate.")
        except Exception as e:
            logger.error(f"ERROR adding documents to Weaviate: {e}")

    return vectorstore
