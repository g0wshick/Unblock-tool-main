from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

import sqlalchemy as sa
from sqlalchemy import ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from storage.models.base import Base

if TYPE_CHECKING:
    from storage.models.channel import Channel
    from storage.models.thread import Thread


class Message(Base):
    """A single Slack message, either a thread root or a reply."""

    __tablename__ = "messages"

    __table_args__ = (
        # Powers keyword search (exact stack trace / error code matches).
        Index("ix_messages_search_vector", "search_vector", postgresql_using="gin"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)  # Slack message ts
    channel_id: Mapped[str] = mapped_column(
        ForeignKey("channels.id"), nullable=False, index=True
    )
    thread_id: Mapped[Optional[str]] = mapped_column(ForeignKey("threads.id"), index=True)
    author: Mapped[Optional[str]] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    posted_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    permalink: Mapped[Optional[str]] = mapped_column(Text)
    search_vector: Mapped[Optional[str]] = mapped_column(
        TSVECTOR, sa.Computed("to_tsvector('english', text)", persisted=True)
    )

    channel: Mapped["Channel"] = relationship()
    thread: Mapped[Optional["Thread"]] = relationship(back_populates="messages")
