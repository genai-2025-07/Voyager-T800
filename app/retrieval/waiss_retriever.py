from typing import Any
import os
from typing import List
from langchain.schema import Document
from langchain_core.retrievers import BaseRetriever
from langchain_openai import OpenAIEmbeddings
from pydantic import ConfigDict
from app.services.weaviate.attraction_db_manager import AttractionDBManager


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
        if self.mode == "similarity":
            vector = self.embeddings.embed_query(query)
            results = self.db.vector_search_chunks(vector, limit=self.limit)
        elif self.mode == "keyword":
            results = self.db.keyword_search_chunks(query, limit=self.limit)
        elif self.mode == "hybrid":
            vector = self.embeddings.embed_query(query)
            results = self.db.hybrid_search_chunks(query, vector, limit=self.limit)
        else:
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
    return RAGAttractionRetriever(db=db, embeddings=embeddings)
