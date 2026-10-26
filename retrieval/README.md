# Retrieval

Dev 3 owns the path from an unblock query to ranked Slack evidence.

```text
query text
  -> Voyage query embedding
  -> Postgres keyword search + pgvector search
  -> reciprocal rank fusion
  -> top Slack-thread summary + citations
```

The final answer is intentionally deterministic for now. Voyage is used for
embeddings only; no LLM is called to write the response.

## Folder guide

```text
retrieval/
  embeddings/       Voyage config, provider wrapper, and embedding service
  search/           DB keyword/vector search, ranking, and public search service
  scripts/          CLI entry points for retrieval maintenance tasks
  tests/            Unit tests for embedding, DB search, and response behavior
  models.py         Retrieval data contracts shared across embeddings/search
  exceptions.py     Retrieval-specific exceptions
```

## Main entry points

- `retrieval.search.RetrievalSearchService` is what the bot/API should call.
- `retrieval.scripts.index_embeddings` indexes real ingested Slack threads.

Run indexing after ingestion has written real `threads` and `messages` rows:

```powershell
python -m retrieval.scripts.index_embeddings
```

Run retrieval tests:

```powershell
python -m unittest discover -s retrieval/tests -p "test_*.py"
```