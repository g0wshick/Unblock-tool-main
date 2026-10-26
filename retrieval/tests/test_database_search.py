import unittest
from datetime import datetime, timezone

from retrieval.models import EmbeddingResult
from retrieval.search import index_missing_thread_embeddings, keyword_search_db


class FakeMappingResult:
	def __init__(self, rows):
		self.rows = rows

	def mappings(self):
		return iter(self.rows)


class FakeSession:
	def __init__(self, rows):
		self.rows = rows
		self.executed = []
		self.merged = []
		self.committed = False

	def execute(self, statement, params=None):
		self.executed.append((str(statement), params or {}))
		return FakeMappingResult(self.rows)

	def merge(self, value):
		self.merged.append(value)

	def commit(self):
		self.committed = True


class FakeEmbeddingService:
	def __init__(self):
		self.calls = []

	def embed_batch(self, texts, input_type="document"):
		self.calls.append((list(texts), input_type))
		return [
			EmbeddingResult(
				vector=[1.0, 0.0, 0.0],
				provider="fake",
				model="fake-model",
				dimension=3,
				input_type=input_type,
			)
			for _ in texts
		]


def db_row(thread_id="thread-1", score=0.75):
	return {
		"thread_id": thread_id,
		"channel_name": "eng-help",
		"thread_text": "Learner API returned 403. Re-auth GitHub SSO fixed it.",
		"first_posted_at": datetime(2026, 9, 20, tzinfo=timezone.utc),
		"author": "alex",
		"permalink": "https://slack.example/thread-1",
		"score": score,
	}


class DatabaseSearchTest(unittest.TestCase):
	def test_keyword_search_db_maps_real_rows_to_search_hits(self):
		session = FakeSession([db_row()])

		hits = keyword_search_db(session, "Learner API 403", limit=5)

		self.assertEqual(hits[0].document.id, "thread-1")
		self.assertEqual(hits[0].document.chunk.channel, "eng-help")
		self.assertEqual(hits[0].document.chunk.permalink, "https://slack.example/thread-1")
		self.assertEqual(hits[0].source, "keyword")
		self.assertIn("plainto_tsquery", session.executed[0][0])

	def test_index_missing_thread_embeddings_embeds_and_stores_real_thread_text(self):
		session = FakeSession([db_row()])
		embedding_service = FakeEmbeddingService()

		indexed_count = index_missing_thread_embeddings(session, embedding_service)

		self.assertEqual(indexed_count, 1)
		self.assertEqual(embedding_service.calls[0][1], "document")
		self.assertIn("Learner API returned 403", embedding_service.calls[0][0][0])
		self.assertEqual(session.merged[0].thread_id, "thread-1")
		self.assertEqual(session.merged[0].model, "fake-model")
		self.assertTrue(session.committed)


if __name__ == "__main__":
	unittest.main()