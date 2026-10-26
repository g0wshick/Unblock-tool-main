"""Embedding provider interfaces and implementations."""

from abc import ABC, abstractmethod
from typing import Sequence

from retrieval.models import EmbeddingInputType


class EmbeddingProvider(ABC):
    """Common contract for the embedding provider used by retrieval services."""

    name: str
    model: str

    @abstractmethod
    def generate_embeddings(
        self,
        texts: Sequence[str],
        input_type: EmbeddingInputType,
    ) -> list[list[float]]:
        """Return one embedding vector per input text."""


class VoyageEmbeddingProvider(EmbeddingProvider):
    """Thin wrapper around Voyage so the rest of the app stays provider-neutral."""

    name = "voyage"

    def __init__(self, api_key: str, model: str) -> None:
        import voyageai

        self.model = model
        self._client = voyageai.Client(api_key=api_key)

    def generate_embeddings(
        self,
        texts: Sequence[str],
        input_type: EmbeddingInputType,
    ) -> list[list[float]]:
        response = self._client.embed(
            list(texts),
            model=self.model,
            input_type=input_type,
        )
        return response.embeddings