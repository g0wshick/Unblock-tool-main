# Import every model module so it registers on Base.metadata and becomes
# visible to Alembic's --autogenerate.
from storage.models.channel import Channel  # noqa: F401
from storage.models.embedding import Embedding  # noqa: F401
from storage.models.feedback import Feedback  # noqa: F401
from storage.models.ingestion_run import IngestionRun  # noqa: F401
from storage.models.message import Message  # noqa: F401
from storage.models.thread import Thread  # noqa: F401
