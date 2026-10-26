"""Data contracts for embeddings and retrieval results."""

from dataclasses import dataclass, field
from typing import Any, Literal


EmbeddingInputType = Literal["document", "query"]
SearchSource = Literal["keyword", "vector"]


@dataclass(frozen=True)
class ThreadChunk:
    """Cleaned Slack thread chunk received from the ingestion pipeline."""

    text: str
    channel: str
    author: str | None = None
    timestamp: str | None = None
    permalink: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EmbeddingResult:
    """Provider-neutral embedding output returned by the service."""

    vector: list[float]
    provider: str
    model: str
    dimension: int
    input_type: EmbeddingInputType


@dataclass(frozen=True)
class EmbeddedThreadChunk:
    """Thread chunk plus its embedding result."""

    chunk: ThreadChunk
    embedding: EmbeddingResult


@dataclass(frozen=True)
class StoredThreadEmbedding:
    """Thread chunk plus its already-generated embedding vector."""

    id: str
    chunk: ThreadChunk
    vector: list[float]


@dataclass(frozen=True)
class SearchHit:
    """One result from either keyword search or vector search."""

    document: StoredThreadEmbedding
    score: float
    rank: int
    source: SearchSource


@dataclass(frozen=True)
class MergedSearchResult:
    """Keyword/vector search result after reciprocal rank fusion."""

    document: StoredThreadEmbedding
    score: float
    keyword_score: float = 0.0
    vector_score: float = 0.0
    keyword_rank: int | None = None
    vector_rank: int | None = None