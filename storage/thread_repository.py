from datetime import datetime, timezone
from typing import Any

from sqlalchemy.dialects.postgresql import insert

from ingestion.models.thread import SlackThread
from storage.db import SessionLocal
from storage.models.channel import Channel
from storage.models.message import Message
from storage.models.thread import Thread


def persist_threads(
    threads: list[SlackThread],
    channel_name: str | None = None,
) -> dict[str, int]:
    """Idempotently upsert a batch of Slack threads and messages."""
    if not threads:
        return {"threads_saved": 0, "messages_saved": 0}

    channel_ids = {thread.channel_id for thread in threads}
    if len(channel_ids) != 1:
        raise ValueError("A persistence batch must contain one channel only")

    channel_id = next(iter(channel_ids))
    channel_values = {
        "id": channel_id,
        "name": channel_name or channel_id,
    }
    thread_values = [
        {"id": thread.thread_ts, "channel_id": thread.channel_id}
        for thread in threads
    ]
    message_values: list[dict[str, Any]] = []
    for thread in threads:
        for message in thread.messages:
            message_values.append(
                {
                    "id": message.ts,
                    "channel_id": message.channel_id,
                    "thread_id": thread.thread_ts,
                    "author": message.user_id,
                    "text": message.text,
                    "posted_at": datetime.fromtimestamp(
                        float(message.ts), tz=timezone.utc
                    ),
                    "permalink": message.permalink,
                }
            )

    session = SessionLocal()
    try:
        channel_insert = insert(Channel)
        session.execute(
            channel_insert.on_conflict_do_update(
                index_elements=[Channel.id],
                set_={"name": channel_insert.excluded.name},
            ),
            [channel_values],
        )

        thread_insert = insert(Thread)
        session.execute(
            thread_insert.on_conflict_do_update(
                index_elements=[Thread.id],
                set_={"channel_id": thread_insert.excluded.channel_id},
            ),
            thread_values,
        )

        if message_values:
            message_insert = insert(Message)
            session.execute(
                message_insert.on_conflict_do_update(
                    index_elements=[Message.id],
                    set_={
                        "channel_id": message_insert.excluded.channel_id,
                        "thread_id": message_insert.excluded.thread_id,
                        "author": message_insert.excluded.author,
                        "text": message_insert.excluded.text,
                        "posted_at": message_insert.excluded.posted_at,
                        "permalink": message_insert.excluded.permalink,
                    },
                ),
                message_values,
            )

        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    return {
        "threads_saved": len(threads),
        "messages_saved": len(message_values),
    }
