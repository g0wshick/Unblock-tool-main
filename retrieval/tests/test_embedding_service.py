import unittest

from retrieval.embeddings import EmbeddingService, EmbeddingProvider
from retrieval.models import ThreadChunk


class FakeProvider(EmbeddingProvider):
	name = "fake"
	model = "fake-model"

	def __init__(self):
		self.calls = []

	def generate_embeddings(self, texts, input_type):
		self.calls.append((list(texts), input_type))
		return [[float(index), 0.1, 0.2] for index, _ in enumerate(texts)]


class EmbeddingServiceTest(unittest.TestCase):
	def test_embed_thread_uses_document_input_type_and_preserves_metadata(self):
		provider = FakeProvider()
		service = EmbeddingService(provider=provider, expected_dimension=3)
		chunk = ThreadChunk(
			text="Learner API 403 fixed by re-authenticating GitHub SSO.",
			channel="eng-help",
			author="alex",
			timestamp="2026-09-20T10:15:00Z",
			permalink="https://slack.example/thread/1",
		)

		embedded = service.embed_thread(chunk)

		self.assertEqual(provider.calls, [([chunk.text], "document")])
		self.assertEqual(embedded.chunk.permalink, chunk.permalink)
		self.assertEqual(embedded.embedding.dimension, 3)
		self.assertEqual(embedded.embedding.input_type, "document")

	def test_embed_query_uses_query_input_type(self):
		provider = FakeProvider()
		service = EmbeddingService(provider=provider, expected_dimension=3)

		result = service.embed_query("Getting forbidden when accessing Learner API")

		self.assertEqual(
			provider.calls,
			[(["Getting forbidden when accessing Learner API"], "query")],
		)
		self.assertEqual(result.input_type, "query")
		self.assertEqual(result.provider, "fake")


if __name__ == "__main__":
	unittest.main()