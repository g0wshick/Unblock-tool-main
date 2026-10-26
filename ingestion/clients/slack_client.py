import asyncio
import logging
import random
from typing import Any

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from ingestion.exceptions import SlackClientError, SlackRateLimitError
from ingestion.models.slack_message import SlackMessage

logger = logging.getLogger(__name__)


class SlackClient:
    def __init__(
        self,
        token: str,
        max_retries: int = 5,
        initial_backoff_seconds: float = 1.0,
    ) -> None:
        self._client = WebClient(token=token)

        self._max_retries = max_retries
        self._initial_backoff_seconds = initial_backoff_seconds

    async def fetch_history_page(
        self,
        channel_id: str,
        cursor: str | None = None,
        oldest: str | None = None,
        latest: str | None = None,
        limit: int = 200,
    ) -> tuple[list[SlackMessage], bool, str | None]:

        response = await self._call_with_retry(
            lambda: self._client.conversations_history(
                channel=channel_id,
                cursor=cursor,
                oldest=oldest,
                latest=latest,
                limit=limit,
                inclusive=False,
            )
        )

        raw_messages = response.get("messages", [])

        messages = [
            self._to_slack_message(
                channel_id=channel_id,
                message=message,
            )
            for message in raw_messages
        ]

        metadata = response.get("response_metadata", {})
        next_cursor = metadata.get("next_cursor")

        return (
            messages,
            bool(response.get("has_more")),
            next_cursor or None,
        )

    async def fetch_thread_replies(
        self,
        channel_id: str,
        thread_ts: str,
        limit: int = 200,
    ) -> list[SlackMessage]:

        cursor: str | None = None
        seen_cursors: set[str] = set()
        result: list[SlackMessage] = []

        while True:
            response = await self._call_with_retry(
                lambda: self._client.conversations_replies(
                    channel=channel_id,
                    ts=thread_ts,
                    cursor=cursor,
                    limit=limit,
                )
            )

            raw_messages = response.get("messages", [])

            result.extend(
                self._to_slack_message(
                    channel_id=channel_id,
                    message=message,
                )
                for message in raw_messages
            )

            metadata = response.get("response_metadata", {})
            cursor = metadata.get("next_cursor") or None

            if not response.get("has_more") or not cursor:
                break

            if cursor in seen_cursors:
                raise SlackClientError(
                    f"Slack repeated a replies cursor for thread {thread_ts}"
                )

            seen_cursors.add(cursor)


        return result

    async def get_permalink(
        self,
        channel_id: str,
        message_ts: str,
    ) -> str | None:

        response = await self._call_with_retry(
            lambda: self._client.chat_getPermalink(
                channel=channel_id,
                message_ts=message_ts,
            )
        )

        return response.get("permalink")

    async def get_channel_name(self, channel_id: str) -> str | None:
        response = await self._call_with_retry(
            lambda: self._client.conversations_info(channel=channel_id)
        )
        channel = response.get("channel", {})
        return channel.get("name")

    async def _call_with_retry(
        self,
        operation: Any,
    ) -> Any:

        for attempt in range(self._max_retries + 1):
            try:
                return await asyncio.to_thread(operation)

            except SlackApiError as exc:
                response = exc.response

                if response.status_code == 429:
                    retry_after = self._get_retry_after(response)

                    if attempt >= self._max_retries:
                        raise SlackRateLimitError(
                            "Slack rate limit persisted after "
                            f"{self._max_retries} retries"
                        ) from exc

                    logger.warning(
                        "Slack rate limit hit. Waiting %.2f seconds. "
                        "attempt=%d/%d",
                        retry_after,
                        attempt + 1,
                        self._max_retries,
                    )

                    await asyncio.sleep(retry_after)
                    continue

                if self._is_retryable(response.status_code):
                    delay = self._backoff_delay(attempt)

                    if attempt >= self._max_retries:
                        raise SlackClientError(
                            f"Slack API failed after "
                            f"{self._max_retries} retries: "
                            f"{response.get('error', 'unknown error')}"
                        ) from exc

                    logger.warning(
                        "Retryable Slack error. "
                        "status=%s delay=%.2f attempt=%d/%d",
                        response.status_code,
                        delay,
                        attempt + 1,
                        self._max_retries,
                    )

                    await asyncio.sleep(delay)
                    continue

                raise SlackClientError(
                    f"Slack API error: "
                    f"{response.get('error', 'unknown error')}"
                ) from exc

            except (TimeoutError, ConnectionError) as exc:
                if attempt >= self._max_retries:
                    raise SlackClientError(
                        "Slack API connection failed after retries"
                    ) from exc

                delay = self._backoff_delay(attempt)

                logger.warning(
                    "Slack connection error. "
                    "delay=%.2f attempt=%d/%d",
                    delay,
                    attempt + 1,
                    self._max_retries,
                )

                await asyncio.sleep(delay)

        raise SlackClientError("Unexpected Slack client failure")

    @staticmethod
    def _get_retry_after(response: Any) -> float:
        headers = getattr(response, "headers", {}) or {}

        value = headers.get("Retry-After", "1")

        try:
            return max(float(value), 0.0)
        except (TypeError, ValueError):
            return 1.0

    def _backoff_delay(self, attempt: int) -> float:
        base = self._initial_backoff_seconds * (2**attempt)

        # Small jitter prevents synchronized retries.
        return base + random.uniform(0, 0.25 * base)

    @staticmethod
    def _is_retryable(status_code: int) -> bool:
        return status_code in {
            408,
            500,
            502,
            503,
            504,
        }

    @staticmethod
    def _to_slack_message(
        channel_id: str,
        message: dict[str, Any],
    ) -> SlackMessage:

        subtype = message.get("subtype")

        return SlackMessage(
            channel_id=channel_id,
            ts=str(message["ts"]),
            thread_ts=message.get("thread_ts"),
            user_id=message.get("user"),
            text=message.get("text", ""),
            subtype=subtype,
            is_bot=(
                subtype == "bot_message"
                or message.get("bot_id") is not None
            ),
            permalink=message.get("permalink"),
            reply_count=int(message.get("reply_count", 0)),
            raw_message_type=message.get("type"),
        )