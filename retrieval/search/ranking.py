"""Merge keyword and vector search results."""

from retrieval.models import MergedSearchResult, SearchHit, StoredThreadEmbedding


def reciprocal_rank_fusion(
    keyword_hits: list[SearchHit],
    vector_hits: list[SearchHit],
    limit: int = 5,
    k: int = 60,
) -> list[MergedSearchResult]:
    """Combine ranked result lists so neither keyword nor vector search dominates."""
    merged: dict[str, _MutableMergedResult] = {}

    for hit in keyword_hits:
        item = merged.setdefault(hit.document.id, _MutableMergedResult(hit.document))
        item.score += 1 / (k + hit.rank)
        item.keyword_score = hit.score
        item.keyword_rank = hit.rank

    for hit in vector_hits:
        item = merged.setdefault(hit.document.id, _MutableMergedResult(hit.document))
        item.score += 1 / (k + hit.rank)
        item.vector_score = hit.score
        item.vector_rank = hit.rank

    results = [item.to_result() for item in merged.values()]
    results.sort(key=lambda result: result.score, reverse=True)
    return results[:limit]


class _MutableMergedResult:
    def __init__(self, document: StoredThreadEmbedding) -> None:
        self.document = document
        self.score = 0.0
        self.keyword_score = 0.0
        self.vector_score = 0.0
        self.keyword_rank = None
        self.vector_rank = None

    def to_result(self) -> MergedSearchResult:
        return MergedSearchResult(
            document=self.document,
            score=self.score,
            keyword_score=self.keyword_score,
            vector_score=self.vector_score,
            keyword_rank=self.keyword_rank,
            vector_rank=self.vector_rank,
        )