from typing import Any
import os
from typing import List
from langchain.schema import Document
from langchain_core.retrievers import BaseRetriever
from langchain_openai import OpenAIEmbeddings
from pydantic import ConfigDict
from app.services.weaviate.attraction_db_manager import AttractionDBManager
import logging

logger = logging.getLogger('app.retrieval.waiss_retriever')


class RAGAttractionRetriever(BaseRetriever):
    """
    LangChain-compatible retriever wrapper for AttractionDBManager.
    Supports similarity, keyword, and hybrid search modes.
    """

    db: Any
    embeddings: Any
    mode: str = os.getenv("RETRIEVER", "hybrid")
    limit: int = int(os.getenv("TOP_K", 5))

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def _get_relevant_documents(self, query: str) -> List[Document]:
        """
        Run retrieval using AttractionDBManager and convert results to LangChain Documents
        """
        search_methods = {
            "similarity": lambda: self.db.vector_search_chunks(self.embeddings.embed_query(query), limit=self.limit),
            "keyword": lambda: self.db.keyword_search_chunks(query, limit=self.limit),
            "hybrid": lambda: self.db.hybrid_search_chunks(query, self.embeddings.embed_query(query), limit=self.limit)
        }

        try:
            results = search_methods[self.mode]()
        except KeyError:
            raise ValueError(f"Unknown retriever mode: {self.mode}")

        docs = []
        for obj in results.objects:
            props = obj.properties.dict() if hasattr(obj.properties, "dict") else obj.properties
            docs.append(
                Document(
                    page_content=props.get("chunk_text", ""),
                    metadata={
                        "uuid": obj.uuid,
                        "name": props.get("name"),
                        "city": props.get("city"),
                        "tags": props.get("tags"),
                        "source": props.get("source"),
                        "score": obj.metadata.score if obj.metadata else None,
                        "distance": obj.metadata.distance if obj.metadata else None,
                    }
                )
            )
        logger.info(f"Succesfully retrieved {len(docs)} documents.")
        return docs

def setup_rag_retriever(
    db: AttractionDBManager
) -> RAGAttractionRetriever:
    """
    Factory function to set up RAG retriever with existing AttractionDBManager.
    """
    embeddings = OpenAIEmbeddings(
        model=os.getenv("EMBED_MODEL", "text-embedding-3-small"),
        openai_api_key=os.getenv("OPENAI_API_KEY")
    )
    
    try:
        retriver = RAGAttractionRetriever(db=db, embeddings=embeddings)
        logger.info("RAG retriever successfully set up.")
        return retriver
    except Exception as e:
        logger.error(f"Failed to set up RAG retriever: {e}")
