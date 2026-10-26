from ingestion.models.thread import SlackThread


class ThreadDeduplicator:

    def deduplicate(
        self,
        threads: list[SlackThread],
    ) -> list[SlackThread]:

        unique: dict[tuple[str, str], SlackThread] = {}

        for thread in threads:
            key = (
                thread.channel_id,
                thread.thread_ts,
            )

            existing = unique.get(key)

            if existing is None:
                unique[key] = thread
                continue

            unique[key] = self._merge(existing, thread)

        return list(unique.values())

    @staticmethod
    def _merge(
        first: SlackThread,
        second: SlackThread,
    ) -> SlackThread:

        messages_by_ts = {
            message.ts: message
            for message in first.messages
        }

        for message in second.messages:
            messages_by_ts[message.ts] = message

        messages = sorted(
            messages_by_ts.values(),
            key=lambda message: float(message.ts),
        )

        return first.model_copy(
            update={
                "messages": messages,
            }
        )