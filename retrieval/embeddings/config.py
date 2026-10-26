"""Environment-based configuration for retrieval embeddings."""

import os

from retrieval.exceptions import ConfigError


try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover - python-dotenv is already in project deps
    pass


EMBEDDINGS_API_KEY = os.environ.get("EMBEDDINGS_API_KEY")
EMBEDDINGS_MODEL = os.environ.get("EMBEDDINGS_MODEL", "voyage-4")

_DEFAULT_DIMENSIONS = {
    "voyage-4": 1024,
    "voyage-4-lite": 1024,
    "voyage-4-large": 2048,
    "voyage-3-lite": 1024,
    "voyage-3": 1024,
}
EMBEDDINGS_DIMENSION = int(
    os.environ.get(
        "EMBEDDINGS_DIMENSION",
        _DEFAULT_DIMENSIONS.get(EMBEDDINGS_MODEL, 1024),
    )
)

MAX_CHUNK_TOKENS = int(os.environ.get("MAX_CHUNK_TOKENS", 500))
EMBEDDINGS_MAX_RETRIES = int(os.environ.get("EMBEDDINGS_MAX_RETRIES", 4))
EMBEDDINGS_RETRY_BASE_DELAY_SECONDS = float(
    os.environ.get("EMBEDDINGS_RETRY_BASE_DELAY", 1.0)
)
EMBEDDINGS_BATCH_SIZE = int(os.environ.get("EMBEDDINGS_BATCH_SIZE", 96))


def validate_embeddings_config() -> None:
    """Raise a clear error early if required embeddings config is missing."""
    if not EMBEDDINGS_API_KEY:
        raise ConfigError(
            "EMBEDDINGS_API_KEY is not set. Copy .env.example to .env and fill it in."
        )
    if not EMBEDDINGS_MODEL:
        raise ConfigError("EMBEDDINGS_MODEL is empty. Set it to a Voyage model.")