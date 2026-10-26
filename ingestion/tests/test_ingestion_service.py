import tempfile
import unittest
from pathlib import Path

from ingestion.models.slack_message import SlackMessage
from ingestion.services.deduplicator import ThreadDeduplicator
from ingestion.services.ingestion_service import IngestionService
from ingestion.services.noise_filter import NoiseFilter
from ingestion.services.thread_grouper import ThreadGrouper
from ingestion.storage.checkpoint import CheckpointStore


class FakeSlackClient:
    def __init__(self, replies):
        self.replies = replies
        self.requested_threads = []
        self.requested_permalinks = []

    async def fetch_thread_replies(self, channel_id, thread_ts):
        self.requested_threads.append((channel_id, thread_ts))
        return self.replies

    async def get_permalink(self, channel_id, message_ts):
        self.requested_permalinks.append((channel_id, message_ts))
        return f"https://slack.example/{channel_id}/{message_ts}"


class FakePaginator:
    def __init__(self, messages):
        self.messages = messages

    async def fetch_channel_messages(self, channel_id, oldest=None):
        return self.messages


class IngestionServiceTest(unittest.IsolatedAsyncioTestCase):
    async def test_incremental_reply_fetches_root_and_defers_checkpoint(self):
        root = SlackMessage(
            channel_id="C123",
            ts="100.0",
            user_id="U1",
            text="Worker returned a 500 error",
            reply_count=1,
        )
        reply = SlackMessage(
            channel_id="C123",
            ts="101.0",
            thread_ts="100.0",
            user_id="U2",
            text="Fixed by restarting the worker",
        )
        slack_client = FakeSlackClient([root, reply])

        with tempfile.TemporaryDirectory() as directory:
            checkpoint_store = CheckpointStore(
                str(Path(directory) / "checkpoints.json")
            )
            checkpoint_store.update("C123", "99.0")
            service = IngestionService(
                slack_client=slack_client,
                paginator=FakePaginator([reply]),
                thread_grouper=ThreadGrouper(),
                noise_filter=NoiseFilter(),
                deduplicator=ThreadDeduplicator(),
                checkpoint_store=checkpoint_store,
            )

            threads = await service.ingest_channel("C123")

            self.assertEqual(slack_client.requested_threads, [("C123", "100.0")])
            self.assertEqual(slack_client.requested_permalinks, [("C123", "100.0")])
            self.assertEqual(len(threads), 1)
            self.assertEqual(threads[0].root_message.ts, "100.0")
            self.assertEqual(
                threads[0].root_message.permalink,
                "https://slack.example/C123/100.0",
            )
            self.assertEqual(len(threads[0].messages), 2)
            self.assertEqual(
                threads[0].messages[0].permalink,
                "https://slack.example/C123/100.0",
            )
            self.assertEqual(checkpoint_store.get("C123"), "99.0")

            service.commit_checkpoint("C123")

            self.assertEqual(checkpoint_store.get("C123"), "101.0")


if __name__ == "__main__":
    unittest.main()
