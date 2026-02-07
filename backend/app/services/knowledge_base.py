"""Knowledge base service -- RAG-ready vector store integration.

Provides an abstraction layer over Pinecone for storing and retrieving
product knowledge, past articles, brand voice guidelines, and market data
used by the agent pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import structlog

from app.config import settings

logger = structlog.get_logger(__name__)


@dataclass
class KnowledgeChunk:
    """A single chunk of knowledge with its embedding metadata."""

    id: str
    text: str
    metadata: dict[str, Any]
    score: float = 0.0


# ── Namespaces ────────────────────────────────────────────────────────────────

NAMESPACE_PRODUCT = "product_info"
NAMESPACE_ARTICLES = "past_articles"
NAMESPACE_BRAND = "brand_voice"
NAMESPACE_MARKET = "market_data"
NAMESPACE_REGULATIONS = "regulations"


class KnowledgeBaseService:
    """Interface to the vector database for RAG-based retrieval.

    On initialisation, if Pinecone credentials are configured the service
    connects to the remote index.  Otherwise it falls back to an in-memory
    store suitable for development and testing.
    """

    def __init__(self) -> None:
        self._index = None
        self._in_memory_store: dict[str, list[KnowledgeChunk]] = {}

        if settings.pinecone_api_key:
            try:
                from pinecone import Pinecone

                pc = Pinecone(api_key=settings.pinecone_api_key)
                self._index = pc.Index(settings.pinecone_index_name)
                logger.info(
                    "knowledge_base_connected",
                    index=settings.pinecone_index_name,
                )
            except Exception as exc:
                logger.warning(
                    "pinecone_init_failed",
                    error=str(exc),
                )
        else:
            logger.info("knowledge_base_in_memory_mode")

    async def upsert(
        self,
        chunks: list[KnowledgeChunk],
        namespace: str = NAMESPACE_PRODUCT,
    ) -> int:
        """Upsert knowledge chunks into the vector store.

        Returns the number of successfully upserted chunks.
        """
        if self._index is not None:
            vectors = []
            for chunk in chunks:
                embedding = await self._get_embedding(chunk.text)
                vectors.append({
                    "id": chunk.id,
                    "values": embedding,
                    "metadata": {**chunk.metadata, "text": chunk.text},
                })
            self._index.upsert(vectors=vectors, namespace=namespace)
            logger.info("knowledge_upserted", count=len(vectors), namespace=namespace)
            return len(vectors)

        # In-memory fallback
        if namespace not in self._in_memory_store:
            self._in_memory_store[namespace] = []
        self._in_memory_store[namespace].extend(chunks)
        return len(chunks)

    async def query(
        self,
        query_text: str,
        *,
        namespace: str = NAMESPACE_PRODUCT,
        top_k: int = 5,
    ) -> list[KnowledgeChunk]:
        """Retrieve the most relevant chunks for a query.

        Returns up to ``top_k`` :class:`KnowledgeChunk` instances sorted by
        descending relevance score.
        """
        if self._index is not None:
            embedding = await self._get_embedding(query_text)
            results = self._index.query(
                vector=embedding,
                top_k=top_k,
                namespace=namespace,
                include_metadata=True,
            )
            chunks = []
            for match in results.get("matches", []):
                meta = match.get("metadata", {})
                chunks.append(
                    KnowledgeChunk(
                        id=match["id"],
                        text=meta.pop("text", ""),
                        metadata=meta,
                        score=match.get("score", 0.0),
                    )
                )
            return chunks

        # In-memory fallback: simple keyword matching
        store = self._in_memory_store.get(namespace, [])
        query_lower = query_text.lower()
        scored = []
        for chunk in store:
            overlap = sum(1 for w in query_lower.split() if w in chunk.text.lower())
            if overlap > 0:
                scored.append((overlap, chunk))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in scored[:top_k]]

    async def _get_embedding(self, text: str) -> list[float]:
        """Generate an embedding vector for the given text.

        Uses OpenAI's text-embedding-3-small model when available,
        otherwise returns a zero vector (development fallback).
        """
        if settings.openai_api_key:
            import openai

            client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
            resp = await client.embeddings.create(
                model="text-embedding-3-small",
                input=text[:8000],
            )
            return resp.data[0].embedding

        # Fallback: 1536-dimensional zero vector
        logger.warning("embedding_fallback", reason="no OpenAI key configured")
        return [0.0] * 1536


# Module-level singleton
knowledge_base = KnowledgeBaseService()
