"""Application service for document and query embeddings."""

import logging
import time
from typing import Sequence

from retrieval.embeddings import config
from retrieval.embeddings.providers import EmbeddingProvider, VoyageEmbeddingProvider
from retrieval.exceptions import ChunkTooLongError, EmbeddingAPIError
from retrieval.models import (
    EmbeddedThreadChunk,
    EmbeddingInputType,
    EmbeddingResult,
    ThreadChunk,
)

logger = logging.getLogger("retrieval.embeddings")

try:
    import tiktoken

    _encoder = tiktoken.get_encoding("cl100k_base")

    def _count_tokens(text: str) -> int:
        return len(_encoder.encode(text))

except ImportError:  # pragma: no cover - exercised when tiktoken is not installed
    logger.warning(
        "tiktoken not installed; falling back to an approximate token count. "
        "Run `pip install tiktoken` for accurate limits."
    )

    def _count_tokens(text: str) -> int:
        word_count = len(text.split())
        return int(word_count / 0.75) + 1


class EmbeddingService:
    """Single entry point for embedding Slack chunks and live user queries."""

    def __init__(
        self,
        provider: EmbeddingProvider | None = None,
        expected_dimension: int = config.EMBEDDINGS_DIMENSION,
    ) -> None:
        self.provider = provider or self._build_provider()
        self.expected_dimension = expected_dimension

    @property
    def provider_name(self) -> str:
        return self.provider.name

    @property
    def model(self) -> str:
        return self.provider.model

    def embed_thread(self, chunk: ThreadChunk) -> EmbeddedThreadChunk:
        """Embed one cleaned Slack thread chunk as a document vector."""
        embedding = self.embed_text(chunk.text, input_type="document")
        return EmbeddedThreadChunk(chunk=chunk, embedding=embedding)

    def embed_query(self, query: str) -> EmbeddingResult:
        """Embed a developer's /unblock query as a query vector."""
        return self.embed_text(query, input_type="query")

    def embed_text(
        self,
        text: str,
        input_type: EmbeddingInputType = "document",
    ) -> EmbeddingResult:
        return self.embed_batch([text], input_type=input_type)[0]

    def embed_batch(
        self,
        texts: Sequence[str],
        input_type: EmbeddingInputType = "document",
    ) -> list[EmbeddingResult]:
        self._validate_texts(texts)

        results: list[EmbeddingResult] = []
        for index in range(0, len(texts), config.EMBEDDINGS_BATCH_SIZE):
            batch = list(texts[index : index + config.EMBEDDINGS_BATCH_SIZE])
            vectors = self._embed_with_retry(batch, input_type=input_type)
            results.extend(self._to_results(vectors, input_type=input_type))
        return results

    def _build_provider(self) -> EmbeddingProvider:
        config.validate_embeddings_config()
        return VoyageEmbeddingProvider(
            api_key=config.EMBEDDINGS_API_KEY,
            model=config.EMBEDDINGS_MODEL,
        )

    def _validate_texts(self, texts: Sequence[str]) -> None:
        if not texts:
            raise EmbeddingAPIError("At least one text value is required for embedding.")

        for text in texts:
            if not text or not text.strip():
                raise EmbeddingAPIError("Cannot embed empty text.")

            token_count = _count_tokens(text)
            if token_count > config.MAX_CHUNK_TOKENS:
                raise ChunkTooLongError(
                    f"Chunk has ~{token_count} tokens, exceeds the "
                    f"{config.MAX_CHUNK_TOKENS} token limit. Either this chunk "
                    "is a genuine outlier or the chunking boundary needs adjusting."
                )

    def _embed_with_retry(
        self,
        batch: Sequence[str],
        input_type: EmbeddingInputType,
    ) -> list[list[float]]:
        last_error = None
        for attempt in range(config.EMBEDDINGS_MAX_RETRIES):
            try:
                return self.provider.generate_embeddings(batch, input_type=input_type)
            except Exception as exc:  # noqa: BLE001 - SDKs raise provider-specific errors
                last_error = exc
                delay = config.EMBEDDINGS_RETRY_BASE_DELAY_SECONDS * (2**attempt)
                logger.warning(
                    "Embedding call failed (attempt %d/%d): %s. Retrying in %.1fs.",
                    attempt + 1,
                    config.EMBEDDINGS_MAX_RETRIES,
                    exc,
                    delay,
                )
                time.sleep(delay)

        raise EmbeddingAPIError(
            "Embedding call failed after "
            f"{config.EMBEDDINGS_MAX_RETRIES} attempts: {last_error}"
        )

    def _to_results(
        self,
        vectors: Sequence[list[float]],
        input_type: EmbeddingInputType,
    ) -> list[EmbeddingResult]:
        results: list[EmbeddingResult] = []
        for vector in vectors:
            dimension = len(vector)
            if dimension != self.expected_dimension:
                raise EmbeddingAPIError(
                    f"Model returned {dimension}-dimension vectors, but config expects "
                    f"{self.expected_dimension}. Update EMBEDDINGS_DIMENSION before "
                    "connecting this to pgvector."
                )

            results.append(
                EmbeddingResult(
                    vector=vector,
                    provider=self.provider.name,
                    model=self.provider.model,
                    dimension=dimension,
                    input_type=input_type,
                )
            )
        return results