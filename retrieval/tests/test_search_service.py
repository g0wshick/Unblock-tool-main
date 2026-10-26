import unittest
from unittest.mock import patch

from retrieval.models import EmbeddingResult, SearchHit, StoredThreadEmbedding, ThreadChunk
from retrieval.search import RetrievalSearchService
from shared.models import SearchRequest


class FakeEmbeddingService:
	def embed_query(self, query):
		return EmbeddingResult(
			vector=[1.0, 0.0, 0.0],
			provider="fake",
			model="fake-model",
			dimension=3,
			input_type="query",
		)


class FakeSessionFactory:
	def __call__(self):
		return self

	def __enter__(self):
		return object()

	def __exit__(self, exc_type, exc, traceback):
		return False


def hit(source, rank, thread_id="thread-learner-api-403", score=1.0):
	return SearchHit(
		document=StoredThreadEmbedding(
			id=thread_id,
			chunk=ThreadChunk(
				text="Learner API 403 was fixed by GitHub SSO re-auth.",
				channel="eng-help",
				author="alex",
				permalink=f"https://slack.example/{thread_id}",
			),
			vector=[1.0, 0.0, 0.0],
		),
		score=score,
		rank=rank,
		source=source,
	)


class RetrievalSearchServiceTest(unittest.TestCase):
	def test_search_returns_shared_response_with_answer_and_citations(self):
		service = RetrievalSearchService(
			embedding_service=FakeEmbeddingService(),
			session_factory=FakeSessionFactory(),
		)

		with patch("retrieval.search.service.keyword_search_db", return_value=[hit("keyword", 1)]), patch(
			"retrieval.search.service.vector_search_db",
			return_value=[hit("vector", 1)],
		):
			response = service.search(SearchRequest(query="Learner API 403"))

		self.assertIn("thread-learner-api-403", response.answer)
		self.assertIn("Top Slack match", response.answer)
		self.assertEqual(response.citations[0].thread_id, "thread-learner-api-403")
		self.assertEqual(
			response.citations[0].permalink,
			"https://slack.example/thread-learner-api-403",
		)

	def test_search_filters_weak_vector_only_results(self):
		service = RetrievalSearchService(
			embedding_service=FakeEmbeddingService(),
			session_factory=FakeSessionFactory(),
		)

		with patch("retrieval.search.service.keyword_search_db", return_value=[]), patch(
			"retrieval.search.service.vector_search_db",
			return_value=[
				hit("vector", 1, thread_id="strong-vector-match", score=0.42),
				hit("vector", 2, thread_id="weak-vector-match", score=0.16),
			],
		):
			response = service.search(SearchRequest(query="payment invoice retry"))

		self.assertEqual([citation.thread_id for citation in response.citations], ["strong-vector-match"])
		self.assertIn("strong-vector-match", response.citations[0].permalink)

	def test_search_returns_no_match_answer_when_no_results_exist(self):
		service = RetrievalSearchService(
			embedding_service=FakeEmbeddingService(),
			session_factory=FakeSessionFactory(),
		)

		with patch("retrieval.search.service.keyword_search_db", return_value=[]), patch(
			"retrieval.search.service.vector_search_db",
			return_value=[],
		):
			response = service.search(SearchRequest(query="Learner API 403"))

		self.assertEqual(
			response.answer,
			"No strong match was found in the indexed Slack threads.",
		)
		self.assertEqual(response.citations, [])


if __name__ == "__main__":
	unittest.main()