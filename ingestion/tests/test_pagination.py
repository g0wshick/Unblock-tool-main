import unittest

from ingestion.exceptions import SlackClientError
from ingestion.models.slack_message import SlackMessage
from ingestion.services.pagination import SlackPaginator


class FakeSlackClient:
    def __init__(self, pages):
        self.pages = iter(pages)
        self.calls = []

    async def fetch_history_page(self, **kwargs):
        self.calls.append(kwargs)
        return next(self.pages)


class SlackPaginatorTest(unittest.IsolatedAsyncioTestCase):
    async def test_fetches_every_cursor_page(self):
        first = SlackMessage(channel_id="C123", ts="1.0", text="first")
        second = SlackMessage(channel_id="C123", ts="2.0", text="second")
        client = FakeSlackClient(
            [([first], True, "cursor-1"), ([second], False, None)]
        )

        messages = await SlackPaginator(client).fetch_channel_messages("C123")

        self.assertEqual([message.ts for message in messages], ["1.0", "2.0"])
        self.assertEqual([call["cursor"] for call in client.calls], [None, "cursor-1"])

    async def test_repeated_cursor_fails_instead_of_looping(self):
        message = SlackMessage(channel_id="C123", ts="1.0", text="first")
        client = FakeSlackClient(
            [([message], True, "cursor-1"), ([message], True, "cursor-1")]
        )

        with self.assertRaises(SlackClientError):
            await SlackPaginator(client).fetch_channel_messages("C123")

        self.assertEqual(len(client.calls), 2)


if __name__ == "__main__":
    unittest.main()
