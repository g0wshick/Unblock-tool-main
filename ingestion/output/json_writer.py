import json
import os
import tempfile
from pathlib import Path

from ingestion.models.thread import SlackThread


class JsonWriter:

    def write(
        self,
        threads: list[SlackThread],
        output_file: str,
    ) -> None:

        path = Path(output_file)

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        payload = {
            "thread_count": len(threads),
            "threads": [
                thread.model_dump(mode="json")
                for thread in threads
            ],
        }

        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
            ) as file:
                temporary_path = Path(file.name)
                json.dump(
                    payload,
                    file,
                    indent=2,
                    ensure_ascii=False,
                )
                file.flush()
                os.fsync(file.fileno())

            os.replace(temporary_path, path)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)