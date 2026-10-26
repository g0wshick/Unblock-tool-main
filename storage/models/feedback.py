from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from storage.models.base import Base


class Feedback(Base):
    """Thumbs up/down reaction captured on a bot answer, for a given query."""

    __tablename__ = "feedback"

    __table_args__ = (sa.CheckConstraint("reaction IN ('up', 'down')", name="reaction_valid"),)

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    thread_ids: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    reaction: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
    )
