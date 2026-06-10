from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.database import Base

if TYPE_CHECKING:
    from app.models.auction_state import AuctionState


class AuctionHistory(Base):
    """Append-only event log for auction replay and UI feed."""

    __tablename__ = "auction_history"

    history_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    auction_state_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("auction_states.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )

    auction_state: Mapped[AuctionState] = relationship(
        "AuctionState",
        back_populates="history",
    )

    def __repr__(self) -> str:
        return f"<AuctionHistory {self.event_type} session={self.auction_state_id}>"
