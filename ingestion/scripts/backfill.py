import argparse
import asyncio
import contextlib
import os
from pathlib import Path

from ingestion.clients.slack_client import SlackClient
from ingestion.config import get_settings
from ingestion.output.json_writer import JsonWriter
from ingestion.services.deduplicator import ThreadDeduplicator
from ingestion.services.ingestion_service import IngestionService
from ingestion.services.noise_filter import NoiseFilter
from ingestion.services.pagination import SlackPaginator
from ingestion.services.thread_grouper import ThreadGrouper
from ingestion.storage.checkpoint import CheckpointStore
from shared.logging_config import configure_logging


@contextlib.contextmanager
def single_process_lock(lock_path: Path):
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a", encoding="utf-8") as lock_file:
        try:
            if os.name == "nt":
                import msvcrt

                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise RuntimeError(
                "Another Slack backfill is already running for this checkpoint."
            ) from exc

        try:
            yield
        finally:
            if os.name == "nt":
                import msvcrt

                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingest Slack engineering threads"
    )

    parser.add_argument(
        "--channel",
        action="append",
        dest="channels",
        help="Slack channel ID. Can be supplied multiple times.",
    )

    parser.add_argument(
        "--output",
        help="Output JSON file.",
    )

    return parser.parse_args()


async def run(args: argparse.Namespace | None = None) -> None:
    args = args or parse_args()
    settings = get_settings()

    channels = list(dict.fromkeys(args.channels or settings.slack_channel_ids))

    if not channels:
        raise ValueError(
            "No Slack channels configured. "
            "Use --channel or SLACK_CHANNEL_IDS."
        )

    slack_client = SlackClient(
        token=settings.slack_bot_token,
        max_retries=settings.slack_max_retries,
        initial_backoff_seconds=(
            settings.slack_initial_backoff_seconds
        ),
    )

    paginator = SlackPaginator(
        slack_client=slack_client,
        page_size=settings.slack_page_size,
    )

    checkpoint_store = CheckpointStore(
        file_path=settings.checkpoint_file,
    )

    service = IngestionService(
        slack_client=slack_client,
        paginator=paginator,
        thread_grouper=ThreadGrouper(),
        noise_filter=NoiseFilter(),
        deduplicator=ThreadDeduplicator(),
        checkpoint_store=checkpoint_store,
    )

    all_threads = []

    for channel_id in channels:
        threads = await service.ingest_channel(
            channel_id=channel_id
        )

        all_threads.extend(threads)

    output_file = args.output or settings.output_file

    JsonWriter().write(
        threads=all_threads,
        output_file=output_file,
    )

    for channel_id in channels:
        service.commit_checkpoint(channel_id)


def main() -> None:
    configure_logging()

    args = parse_args()
    settings = get_settings()
    checkpoint_path = Path(settings.checkpoint_file)
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = checkpoint_path.with_suffix(
        checkpoint_path.suffix + ".run.lock"
    )

    with single_process_lock(lock_path):
        asyncio.run(run(args))


if __name__ == "__main__":
    main()