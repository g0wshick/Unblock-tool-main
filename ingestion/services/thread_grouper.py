from collections import defaultdict

from ingestion.models.slack_message import SlackMessage
from ingestion.models.thread import SlackThread


class ThreadGrouper:

    def group(
        self,
        messages: list[SlackMessage],
    ) -> list[SlackThread]:

        grouped: dict[str, list[SlackMessage]] = defaultdict(list)

        for message in messages:
            thread_ts = message.thread_ts or message.ts

            grouped[thread_ts].append(message)

        threads: list[SlackThread] = []

        for thread_ts, thread_messages in grouped.items():

            ordered_messages = sorted(
                thread_messages,
                key=lambda message: float(message.ts),
            )

            root_message = next(
                (
                    message
                    for message in ordered_messages
                    if message.ts == thread_ts
                ),
                ordered_messages[0],
            )

            threads.append(
                SlackThread(
                    channel_id=root_message.channel_id,
                    thread_ts=thread_ts,
                    root_message=root_message,
                    messages=ordered_messages,
                    permalink=root_message.permalink,
                )
            )

        return sorted(
            threads,
            key=lambda thread: float(thread.thread_ts),
        )