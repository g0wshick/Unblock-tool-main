import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import HTTPException

import main
from ingestion.models.slack_message import SlackMessage
from ingestion.models.thread import SlackThread
from shared.models import Citation, SearchResponse
from storage.thread_repository import persist_threads


class ThreadRepositoryTest(unittest.TestCase):
    def test_persists_channel_thread_and_messages_in_one_transaction(self):
        root = SlackMessage(
            channel_id="C123",
            ts="1700000000.000001",
            user_id="U1",
            text="Worker returned a 500 error",
            permalink="https://slack.example/root",
        )
        reply = SlackMessage(
            channel_id="C123",
            ts="1700000001.000001",
            thread_ts=root.ts,
            user_id="U2",
            text="Fixed by restarting the worker",
        )
        thread = SlackThread(
            channel_id="C123",
            thread_ts=root.ts,
            root_message=root,
            messages=[root, reply],
            permalink=root.permalink,
        )
        session = Mock()

        with patch("storage.thread_repository.SessionLocal", return_value=session):
            counts = persist_threads([thread], "engineering-help")

        self.assertEqual(counts, {"threads_saved": 1, "messages_saved": 2})
        self.assertEqual(session.execute.call_count, 3)
        self.assertEqual(
            session.execute.call_args_list[0].args[1],
            [{"id": "C123", "name": "engineering-help"}],
        )
        self.assertEqual(
            session.execute.call_args_list[1].args[1],
            [{"id": root.ts, "channel_id": "C123"}],
        )
        stored_messages = session.execute.call_args_list[2].args[1]
        self.assertEqual([message["id"] for message in stored_messages], [root.ts, reply.ts])
        self.assertEqual(stored_messages[0]["thread_id"], root.ts)
        self.assertEqual(stored_messages[0]["text"], root.text)
        session.commit.assert_called_once()
        session.rollback.assert_not_called()
        session.close.assert_called_once()

    def test_rolls_back_when_a_database_write_fails(self):
        thread = SlackThread(
            channel_id="C123",
            thread_ts="1700000000.000001",
            root_message=SlackMessage(
                channel_id="C123",
                ts="1700000000.000001",
                text="A 500 error",
            ),
            messages=[],
        )
        session = Mock()
        session.execute.side_effect = RuntimeError("database unavailable")

        with patch("storage.thread_repository.SessionLocal", return_value=session):
            with self.assertRaisesRegex(RuntimeError, "database unavailable"):
                persist_threads([thread])

        session.commit.assert_not_called()
        session.rollback.assert_called_once()
        session.close.assert_called_once()

    def test_empty_batch_does_not_open_a_database_session(self):
        with patch("storage.thread_repository.SessionLocal") as session_factory:
            counts = persist_threads([])

        self.assertEqual(counts, {"threads_saved": 0, "messages_saved": 0})
        session_factory.assert_not_called()


class IngestionApiTest(unittest.IsolatedAsyncioTestCase):
    async def test_persists_and_indexes_embeddings_before_committing_checkpoint(self):
        events = []
        thread = SlackThread(
            channel_id="C123",
            thread_ts="1700000000.000001",
            root_message=SlackMessage(
                channel_id="C123",
                ts="1700000000.000001",
                text="A 500 error was fixed",
            ),
            messages=[],
        )

        class FakeSlackClient:
            def __init__(self, **kwargs):
                pass

            async def get_channel_name(self, channel_id):
                events.append("fetch_channel_name")
                return "engineering-help"

        class FakeIngestionService:
            def __init__(self, **kwargs):
                pass

            async def ingest_channel(self, channel_id):
                events.append("ingest_slack")
                return [thread]

            def commit_checkpoint(self, channel_id):
                events.append("commit_checkpoint")

        async def run_sync_in_thread(function, *args):
            if function is main.persist_threads:
                events.append("persist_database")
            elif function is main.index_missing_embeddings:
                events.append("index_embeddings")
            return function(*args)

        settings = SimpleNamespace(
            slack_bot_token="test-token",
            slack_max_retries=1,
            slack_initial_backoff_seconds=0.1,
            slack_page_size=200,
            checkpoint_file="/tmp/checkpoints.json",
        )

        with (
            patch("main.get_settings", return_value=settings),
            patch("main.SlackClient", FakeSlackClient),
            patch("main.SlackPaginator"),
            patch("main.ThreadGrouper"),
            patch("main.NoiseFilter"),
            patch("main.ThreadDeduplicator"),
            patch("main.CheckpointStore"),
            patch("main.IngestionService", FakeIngestionService),
            patch(
                "main.persist_threads",
                return_value={"threads_saved": 1, "messages_saved": 1},
            ),
            patch("main.index_missing_embeddings", return_value=1),
            patch("main.run_in_threadpool", new=run_sync_in_thread),
        ):
            response = await main.ingest_channel("C123")

        self.assertEqual(
            events,
            [
                "fetch_channel_name",
                "ingest_slack",
                "persist_database",
                "index_embeddings",
                "commit_checkpoint",
            ],
        )
        self.assertEqual(response.channel_id, "C123")
        self.assertEqual(response.threads_saved, 1)
        self.assertEqual(response.embeddings_indexed, 1)

    def test_api_key_is_required_and_compared(self):
        with patch.dict(os.environ, {"INGESTION_API_KEY": "local-test-key"}):
            main.require_api_key("local-test-key")
            with self.assertRaises(HTTPException) as error:
                main.require_api_key("wrong-key")

        self.assertEqual(error.exception.status_code, 401)

    async def test_unblock_endpoint_returns_retrieval_response(self):
        async def run_sync_in_thread(function, *args):
            return function(*args)

        expected_response = SearchResponse(
            answer="Users saw access denied because reset-session tokens missed billing scopes.",
            citations=[
                Citation(
                    thread_id="1700000000.000001",
                    permalink="https://slack.example/thread",
                    snippet="Password reset token missed billing:read scope.",
                )
            ],
        )

        with (
            patch("main.search_unblock", return_value=expected_response) as search_unblock,
            patch("main.run_in_threadpool", new=run_sync_in_thread),
        ):
            response = await main.unblock(main.SearchRequest(query="access denied after password reset"))

        search_unblock.assert_called_once()
        self.assertEqual(response, expected_response)

    async def test_unblock_endpoint_rejects_blank_query(self):
        request = main.SearchRequest(query="   ")

        with self.assertRaises(HTTPException) as error:
            await main.unblock(request)

        self.assertEqual(error.exception.status_code, 422)


if __name__ == "__main__":
    unittest.main()
