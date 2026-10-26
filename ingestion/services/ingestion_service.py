import logging

from ingestion.clients.slack_client import SlackClient
from ingestion.models.slack_message import SlackMessage
from ingestion.models.thread import SlackThread
from ingestion.services.deduplicator import ThreadDeduplicator
from ingestion.services.noise_filter import NoiseFilter
from ingestion.services.pagination import SlackPaginator
from ingestion.services.thread_grouper import ThreadGrouper
from ingestion.storage.checkpoint import CheckpointStore

logger = logging.getLogger(__name__)


class IngestionService:

    def __init__(
        self,
        slack_client: SlackClient,
        paginator: SlackPaginator,
        thread_grouper: ThreadGrouper,
        noise_filter: NoiseFilter,
        deduplicator: ThreadDeduplicator,
        checkpoint_store: CheckpointStore,
    ) -> None:

        self._slack_client = slack_client
        self._paginator = paginator
        self._thread_grouper = thread_grouper
        self._noise_filter = noise_filter
        self._deduplicator = deduplicator
        self._checkpoint_store = checkpoint_store
        self._pending_checkpoints: dict[str, str] = {}

    async def ingest_channel(
        self,
        channel_id: str,
    ) -> list[SlackThread]:

        checkpoint = self._checkpoint_store.get(channel_id)

        logger.info(
            "Starting ingestion. channel=%s checkpoint=%s",
            channel_id,
            checkpoint,
        )

        messages = await self._paginator.fetch_channel_messages(
            channel_id=channel_id,
            oldest=checkpoint,
        )

        if not messages:
            logger.info(
                "No new messages. channel=%s",
                channel_id,
            )
            return []

        threads = await self._build_threads(
            channel_id=channel_id,
            messages=messages,
        )

        threads = self._deduplicator.deduplicate(threads)

        useful_threads = [
            thread
            for thread in threads
            if self._noise_filter.has_useful_signal(thread)
        ]
        useful_threads = await self._attach_thread_permalinks(useful_threads)

        latest_timestamp = max(
            message.ts
            for message in messages
        )

        self._pending_checkpoints[channel_id] = latest_timestamp

        logger.info(
            "Ingestion completed. "
            "channel=%s messages=%d threads=%d useful_threads=%d",
            channel_id,
            len(messages),
            len(threads),
            len(useful_threads),
        )

        return useful_threads

    async def _attach_thread_permalinks(
        self,
        threads: list[SlackThread],
    ) -> list[SlackThread]:
        enriched_threads: list[SlackThread] = []

        for thread in threads:
            if thread.permalink:
                enriched_threads.append(thread)
                continue

            permalink = await self._slack_client.get_permalink(
                channel_id=thread.channel_id,
                message_ts=thread.thread_ts,
            )
            if permalink is None:
                enriched_threads.append(thread)
                continue

            root_message = thread.root_message.model_copy(
                update={"permalink": permalink}
            )
            messages = [
                message.model_copy(update={"permalink": permalink})
                if message.ts == thread.thread_ts
                else message
                for message in thread.messages
            ]
            enriched_threads.append(
                thread.model_copy(
                    update={
                        "root_message": root_message,
                        "messages": messages,
                        "permalink": permalink,
                    }
                )
            )

        return enriched_threads

    def commit_checkpoint(self, channel_id: str) -> None:
        """Advance a channel after its output has been durably written."""
        timestamp = self._pending_checkpoints.get(channel_id)
        if timestamp is None:
            return

        self._checkpoint_store.update(channel_id, timestamp)
        del self._pending_checkpoints[channel_id]

    async def _build_threads(
        self,
        channel_id: str,
        messages: list[SlackMessage],
    ) -> list[SlackThread]:

        cleaned_messages = self._noise_filter.filter_messages(
            messages
        )

        all_thread_messages = list(cleaned_messages)
        thread_roots_to_fetch = {
            message.thread_ts
            if message.thread_ts is not None
            else message.ts
            for message in cleaned_messages
            if message.thread_ts is not None or message.reply_count > 0
        }

        for thread_ts in sorted(thread_roots_to_fetch, key=float):

            replies = await self._slack_client.fetch_thread_replies(
                channel_id=channel_id,
                thread_ts=thread_ts,
            )

            cleaned_replies = self._noise_filter.filter_messages(
                replies
            )

            existing_ts = {
                message.ts
                for message in all_thread_messages
            }

            all_thread_messages.extend(
                reply
                for reply in cleaned_replies
                if reply.ts not in existing_ts
            )

        threads = self._thread_grouper.group(
            all_thread_messages
        )

        return threads