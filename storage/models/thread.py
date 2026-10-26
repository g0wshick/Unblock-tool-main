from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

import sqlalchemy as sa
from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from storage.models.base import Base

if TYPE_CHECKING:
    from storage.models.channel import Channel
    from storage.models.embedding import Embedding
    from storage.models.message import Message


class Thread(Base):
    """A grouped Slack conversation: a root message plus its replies."""

    __tablename__ = "threads"

    id: Mapped[str] = mapped_column(Text, primary_key=True)  # Slack thread_ts (root message's ts)
    channel_id: Mapped[str] = mapped_column(
        ForeignKey("channels.id"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
    )

    channel: Mapped["Channel"] = relationship()
    messages: Mapped[list["Message"]] = relationship(back_populates="thread")
    embedding: Mapped[Optional["Embedding"]] = relationship(back_populates="thread")
