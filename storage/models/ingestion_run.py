from __future__ import annotations

from datetime import datetime
from typing import Optional

import sqlalchemy as sa
from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from storage.models.base import Base


class IngestionRun(Base):
    """One Slack backfill/sync run for a channel (Dev 1's ingestion pipeline)."""

    __tablename__ = "ingestion_runs"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    channel_id: Mapped[Optional[str]] = mapped_column(ForeignKey("channels.id"), index=True)
    started_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(sa.DateTime(timezone=True))
    status: Mapped[str] = mapped_column(sa.String(30), nullable=False)
    messages_fetched: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default=sa.text("0"))
    threads_processed: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default=sa.text("0"))
    messages_filtered: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default=sa.text("0"))
    chunks_created: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default=sa.text("0"))
    errors_count: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default=sa.text("0"))
    error_message: Mapped[Optional[str]] = mapped_column(Text)
