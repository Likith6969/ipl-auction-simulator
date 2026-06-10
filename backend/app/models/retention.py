from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, SmallInteger, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.domain.enums import RETENTION_COSTS

if TYPE_CHECKING:
    from app.models.auction_state import AuctionState
    from app.models.player import Player
    from app.models.team import Team


class Retention(Base):
    """Pre-auction retention: exactly 3 slots per team per session."""

    __tablename__ = "retentions"
    __table_args__ = (
        UniqueConstraint(
            "auction_state_id",
            "team_id",
            "retention_slot",
            name="uq_retention_team_slot",
        ),
        UniqueConstraint(
            "auction_state_id",
            "player_id",
            name="uq_retention_player_session",
        ),
    )

    retention_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    auction_state_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("auction_states.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    team_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("teams.team_id"),
        nullable=False,
        index=True,
    )
    player_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("players.player_id"),
        nullable=False,
        index=True,
    )
    retention_slot: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    retention_cost_cr: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    auction_state: Mapped[AuctionState] = relationship(
        "AuctionState",
        back_populates="retentions",
    )
    team: Mapped[Team] = relationship("Team", back_populates="retentions")
    player: Mapped[Player] = relationship("Player", back_populates="retentions")

    @staticmethod
    def cost_for_slot(slot: int) -> Decimal:
        if slot not in RETENTION_COSTS:
            raise ValueError(f"Invalid retention slot: {slot}. Must be 1, 2, or 3.")
        return Decimal(str(RETENTION_COSTS[slot]))

    def __repr__(self) -> str:
        return (
            f"<Retention team={self.team_id} player={self.player_id} "
            f"slot={self.retention_slot} cost={self.retention_cost_cr}>"
        )
