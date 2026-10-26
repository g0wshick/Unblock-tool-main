"""CLI helper to embed real ingested Slack threads into the embeddings table."""

from retrieval.exceptions import ConfigError
from retrieval.search import index_missing_thread_embeddings
from storage.db import SessionLocal


def main() -> None:
    try:
        with SessionLocal() as session:
            indexed_count = index_missing_thread_embeddings(session)
    except ConfigError as exc:
        print(f"Cannot index thread embeddings: {exc}")
        print("Set EMBEDDINGS_API_KEY in .env or in this terminal.")
        return

    print(f"Indexed {indexed_count} thread embeddings.")


if __name__ == "__main__":
    main()