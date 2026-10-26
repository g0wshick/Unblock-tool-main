"""DB-backed retrieval over ingested Slack threads."""

from collections.abc import Iterable
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from retrieval.embeddings import EmbeddingService
from retrieval.models import SearchHit, StoredThreadEmbedding, ThreadChunk
from storage.models.embedding import Embedding


THREAD_TEXT_SEPARATOR = "\n---\n"


def index_missing_thread_embeddings(
    session: Session,
    embedding_service: EmbeddingService | None = None,
    limit: int | None = None,
) -> int:
    """Embed real Slack threads that do not yet have rows in embeddings."""
    service = embedding_service or EmbeddingService()
    rows = list(_fetch_threads_missing_embeddings(session, limit=limit))
    if not rows:
        return 0

    chunks = [_row_to_thread_document(row) for row in rows]
    embeddings = service.embed_batch([chunk.chunk.text for chunk in chunks], input_type="document")

    for chunk, embedding in zip(chunks, embeddings):
        session.merge(
            Embedding(
                thread_id=chunk.id,
                embedding=embedding.vector,
                model=embedding.model,
            )
        )

    session.commit()
    return len(chunks)


def keyword_search_db(
    session: Session,
    query: str,
    limit: int = 10,
) -> list[SearchHit]:
    """Search ingested Slack messages with Postgres full-text search."""
    rows = session.execute(
        sa.text(
            """
            SELECT
                t.id AS thread_id,
                c.name AS channel_name,
                string_agg(m.text, :separator ORDER BY m.posted_at) AS thread_text,
                min(m.posted_at) AS first_posted_at,
                (array_remove(array_agg(m.author ORDER BY m.posted_at), NULL))[1] AS author,
                (array_remove(array_agg(m.permalink ORDER BY m.posted_at), NULL))[1] AS permalink,
                max(ts_rank_cd(m.search_vector, plainto_tsquery('english', :query))) AS score
            FROM threads t
            JOIN channels c ON c.id = t.channel_id
            JOIN messages m ON COALESCE(m.thread_id, m.id) = t.id
            WHERE m.search_vector @@ plainto_tsquery('english', :query)
            GROUP BY t.id, c.name
            ORDER BY score DESC, first_posted_at DESC
            LIMIT :limit
            """
        ),
        {"query": query, "limit": limit, "separator": THREAD_TEXT_SEPARATOR},
    ).mappings()

    return [
        SearchHit(
            document=_row_to_thread_document(row),
            score=float(row["score"] or 0.0),
            rank=rank,
            source="keyword",
        )
        for rank, row in enumerate(rows, start=1)
    ]


def vector_search_db(
    session: Session,
    query_vector: list[float],
    limit: int = 10,
) -> list[SearchHit]:
    """Search embedded Slack threads with pgvector cosine similarity."""
    rows = session.execute(
        sa.text(
            """
            SELECT
                t.id AS thread_id,
                c.name AS channel_name,
                string_agg(m.text, :separator ORDER BY m.posted_at) AS thread_text,
                min(m.posted_at) AS first_posted_at,
                (array_remove(array_agg(m.author ORDER BY m.posted_at), NULL))[1] AS author,
                (array_remove(array_agg(m.permalink ORDER BY m.posted_at), NULL))[1] AS permalink,
                1 - (e.embedding <=> CAST(:query_vector AS vector)) AS score
            FROM embeddings e
            JOIN threads t ON t.id = e.thread_id
            JOIN channels c ON c.id = t.channel_id
            JOIN messages m ON COALESCE(m.thread_id, m.id) = t.id
            GROUP BY t.id, c.name, e.embedding
            ORDER BY e.embedding <=> CAST(:query_vector AS vector)
            LIMIT :limit
            """
        ),
        {
            "query_vector": _to_pgvector_literal(query_vector),
            "limit": limit,
            "separator": THREAD_TEXT_SEPARATOR,
        },
    ).mappings()

    return [
        SearchHit(
            document=_row_to_thread_document(row, vector=query_vector),
            score=float(row["score"] or 0.0),
            rank=rank,
            source="vector",
        )
        for rank, row in enumerate(rows, start=1)
    ]


def _fetch_threads_missing_embeddings(
    session: Session,
    limit: int | None,
) -> Iterable[dict[str, Any]]:
    sql = """
        SELECT
            t.id AS thread_id,
            c.name AS channel_name,
            string_agg(m.text, :separator ORDER BY m.posted_at) AS thread_text,
            min(m.posted_at) AS first_posted_at,
            (array_remove(array_agg(m.author ORDER BY m.posted_at), NULL))[1] AS author,
            (array_remove(array_agg(m.permalink ORDER BY m.posted_at), NULL))[1] AS permalink
        FROM threads t
        JOIN channels c ON c.id = t.channel_id
        JOIN messages m ON COALESCE(m.thread_id, m.id) = t.id
        LEFT JOIN embeddings e ON e.thread_id = t.id
        WHERE e.thread_id IS NULL
        GROUP BY t.id, c.name
        ORDER BY first_posted_at ASC
    """
    params: dict[str, Any] = {"separator": THREAD_TEXT_SEPARATOR}
    if limit is not None:
        sql += " LIMIT :limit"
        params["limit"] = limit

    return session.execute(sa.text(sql), params).mappings()


def _row_to_thread_document(
    row: dict[str, Any],
    vector: list[float] | None = None,
) -> StoredThreadEmbedding:
    return StoredThreadEmbedding(
        id=row["thread_id"],
        chunk=ThreadChunk(
            text=row["thread_text"] or "",
            channel=row["channel_name"],
            author=row["author"],
            timestamp=_to_iso_timestamp(row.get("first_posted_at")),
            permalink=row["permalink"],
            metadata={"source": "postgres"},
        ),
        vector=vector or [],
    )


def _to_pgvector_literal(vector: list[float]) -> str:
    return "[" + ",".join(str(value) for value in vector) + "]"


def _to_iso_timestamp(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)