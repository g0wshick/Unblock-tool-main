class IngestionError(Exception):
    """Base exception for ingestion failures."""


class SlackClientError(IngestionError):
    """Raised when Slack API interaction fails."""


class SlackRateLimitError(SlackClientError):
    """Raised when Slack rate limiting cannot be recovered."""


class CheckpointError(IngestionError):
    """Raised when checkpoint persistence fails."""


class ThreadGroupingError(IngestionError):
    """Raised when thread grouping fails."""