from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, SmallInteger, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.auction_state import AuctionState
    from app.models.player import Player
    from app.models.team import Team


class Bid(Base):
    """Bid placed during auction for a player lot within a session."""

    __tablename__ = "bids"

    bid_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    auction_state_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("auction_states.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    player_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("players.player_id"),
        nullable=False,
        index=True,
    )
    team_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("teams.team_id"),
        nullable=False,
        index=True,
    )
    bid_amount_cr: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    bid_sequence: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    is_winning: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    auction_state: Mapped[AuctionState] = relationship(
        "AuctionState",
        back_populates="bids",
    )
    player: Mapped[Player] = relationship("Player", back_populates="bids")
    team: Mapped[Team] = relationship("Team", back_populates="bids")

    def __repr__(self) -> str:
        return (
            f"<Bid team={self.team_id} player={self.player_id} "
            f"amount={self.bid_amount_cr} winning={self.is_winning}>"
        )
