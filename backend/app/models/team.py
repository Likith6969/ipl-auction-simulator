from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.auction_state import AuctionState
    from app.models.bid import Bid
    from app.models.player import Player
    from app.models.retention import Retention


class Team(Base):
    """Franchise reference data seeded from data/teams.csv."""

    __tablename__ = "teams"

    team_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    team_name: Mapped[str] = mapped_column(String(64), nullable=False)
    short_name: Mapped[str] = mapped_column(String(8), nullable=False, unique=True, index=True)

    players: Mapped[list[Player]] = relationship(
        "Player",
        back_populates="franchise",
        primaryjoin="Team.short_name == foreign(Player.current_team)",
        viewonly=True,
    )
    auction_sessions: Mapped[list[AuctionState]] = relationship(
        "AuctionState",
        back_populates="user_team",
        foreign_keys="AuctionState.user_team_id",
    )
    retentions: Mapped[list[Retention]] = relationship("Retention", back_populates="team")
    bids: Mapped[list[Bid]] = relationship("Bid", back_populates="team")

    def __repr__(self) -> str:
        return f"<Team {self.short_name} ({self.team_name})>"
