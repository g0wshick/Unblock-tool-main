import logging

from ingestion.clients.slack_client import SlackClient
from ingestion.exceptions import SlackClientError
from ingestion.models.slack_message import SlackMessage

logger = logging.getLogger(__name__)


class SlackPaginator:
    def __init__(
        self,
        slack_client: SlackClient,
        page_size: int = 200,
    ) -> None:
        self._slack_client = slack_client
        self._page_size = page_size

    async def fetch_channel_messages(
        self,
        channel_id: str,
        oldest: str | None = None,
    ) -> list[SlackMessage]:

        cursor: str | None = None
        seen_cursors: set[str] = set()
        messages: list[SlackMessage] = []

        page_number = 0

        while True:
            page_number += 1

            logger.info(
                "Fetching Slack history. "
                "channel=%s page=%d cursor=%s",
                channel_id,
                page_number,
                bool(cursor),
            )

            page_messages, has_more, next_cursor = (
                await self._slack_client.fetch_history_page(
                    channel_id=channel_id,
                    cursor=cursor,
                    oldest=oldest,
                    limit=self._page_size,
                )
            )

            messages.extend(page_messages)

            logger.info(
                "Slack page fetched. "
                "channel=%s page=%d messages=%d total=%d",
                channel_id,
                page_number,
                len(page_messages),
                len(messages),
            )

            if not has_more or not next_cursor:
                break

            if next_cursor in seen_cursors:
                raise SlackClientError(
                    f"Slack repeated a history cursor for channel {channel_id}"
                )

            seen_cursors.add(next_cursor)
            cursor = next_cursor

        return messages