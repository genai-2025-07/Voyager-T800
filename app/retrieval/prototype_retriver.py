import os
import logging
from langchain_openai import OpenAIEmbeddings
from app.memory.database_prototype_setup import create_weaviate_db_with_loaded_documents

logger = logging.getLogger(__name__)

# Set OpenAI API key for embeddings
try:
    openai_key = os.getenv("OPENAI_API_KEY")
except Exception as e:
    logger.error(f"ERROR exporting OpenAI API key: {e}")

class RAGPrototype:
    """
    Class to initialize and manage a RAG (Retrieval-Augmented Generation) prototype
    with Weaviate as the vector store and OpenAI embeddings.

    Attributes:
        embeddings_dir (str): Directory where embeddings are stored.
        embed_model (str): Embedding model to use.
        retriever_type (str): Type of retriever ('similarity' or 'mmr').
        top_k (int): Number of top documents to retrieve.
        mmr_lambda (float): Lambda parameter for MMR retriever.
        embeddings (OpenAIEmbeddings): Embedding model instance.
        vectorstore (Weaviate): Weaviate vector store instance.
        retriever: Retriever instance based on the specified type.

    Methods:
        get_retriever(): Returns the initialized retriever.
        get_vectorstore(): Returns the initialized vector store.
        get_embeddings(): Returns the embedding model instance.
    """
    def __init__(self, embeddings_dir="data/embeddings"):
        self.embeddings_dir = embeddings_dir
        self.embed_model = os.getenv('EMBED_MODEL', 'text-embedding-3-small')
        self.retriever_type = os.getenv('RETRIVER', 'similarity').lower()
        self.top_k = int(os.getenv('TOP_K', '5'))
        self.fetch_k = int(os.getenv('FETCH_K', '10'))
        self.mmr_lambda = float(os.getenv('MMR_LAMBDA', '0.5'))

        # Embeddings initialization
        self.embeddings = OpenAIEmbeddings(
            model=self.embed_model,
            openai_api_key=os.getenv("OPENAI_API_KEY")
        )

        # Vectorstore (Weaviate) initialization
        try:
            self.vectorstore = create_weaviate_db_with_loaded_documents(self.embeddings, self.embeddings_dir)
            logger.info("Vectorstore initialized")
        except Exception as e:
            logger.error(f"ERROR initializing vectorstore: {e}")

        # Retriever initialization
        try:
            self.retriever = self._init_retriever()
            logger.info(f"Retriever initialized: {self.retriever_type.upper()}")
        except Exception as e:
            logger.error(f"ERROR initializing retriever: {e}")

    def _init_retriever(self):
        """
        Initialize retriever based on type from .env
        Options: 'similarity' or 'mmr'
        """
        if self.retriever_type == 'similarity':
            return self.vectorstore.as_retriever(
                search_type="similarity",
                search_kwargs={"k": self.top_k}
            )
        elif self.retriever_type == 'mmr':
            return self.vectorstore.as_retriever(
                search_type="mmr",
                search_kwargs={"k": self.top_k, "fetch_k": self.fetch_k, "lambda_mult": self.mmr_lambda}
            )
        else:
            logger.error(f"Unknown RETRIVER type: {self.retriever_type}")
            #raise ValueError(f"Unknown RETRIVER type: {self.retriever_type}")

    def get_retriever(self):
        return self.retriever

    def get_vectorstore(self):
        return self.vectorstore

    def get_embeddings(self):
        return self.embeddings
