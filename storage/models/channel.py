from __future__ import annotations

from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column

from storage.models.base import Base


class Channel(Base):
    """A monitored Slack channel."""

    __tablename__ = "channels"

    id: Mapped[str] = mapped_column(Text, primary_key=True)  # Slack channel ID, e.g. C0123ABCD456
    name: Mapped[str] = mapped_column(Text, nullable=False)
