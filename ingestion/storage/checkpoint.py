import json
import os
from pathlib import Path

from ingestion.exceptions import CheckpointError


class CheckpointStore:

    def __init__(self, file_path: str) -> None:
        self._path = Path(file_path)

    def get(self, channel_id: str) -> str | None:

        data = self._read()

        return data.get(channel_id)

    def update(
        self,
        channel_id: str,
        timestamp: str,
    ) -> None:

        data = self._read()

        current = data.get(channel_id)

        if current is not None:
            if float(timestamp) <= float(current):
                return

        data[channel_id] = timestamp

        self._write(data)

    def _read(self) -> dict[str, str]:

        try:
            if not self._path.exists():
                return {}

            with self._path.open(
                "r",
                encoding="utf-8",
            ) as file:
                data = json.load(file)

            if not isinstance(data, dict) or any(
                not isinstance(channel_id, str)
                or not isinstance(timestamp, str)
                for channel_id, timestamp in data.items()
            ):
                raise CheckpointError(
                    f"Invalid checkpoint data in: {self._path}"
                )

            return data

        except (OSError, json.JSONDecodeError) as exc:
            raise CheckpointError(
                f"Failed to read checkpoint file: {self._path}"
            ) from exc

    def _write(
        self,
        data: dict[str, str],
    ) -> None:

        try:
            self._path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            temporary = self._path.with_suffix(self._path.suffix + ".tmp")

            with temporary.open(
                "w",
                encoding="utf-8",
            ) as file:
                json.dump(
                    data,
                    file,
                    indent=2,
                    sort_keys=True,
                )
                file.flush()
                os.fsync(file.fileno())

            temporary.replace(self._path)

        except OSError as exc:
            raise CheckpointError(
                f"Failed to write checkpoint file: {self._path}"
            ) from exc