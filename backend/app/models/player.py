from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, Integer, Numeric, SmallInteger, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.domain.enums import PlayerStatus

if TYPE_CHECKING:
    from app.models.auction_state import AuctionState
    from app.models.bid import Bid
    from app.models.retention import Retention
    from app.models.team import Team


class Player(Base):
    """Player pool seeded from data/players_data_set(ipl).csv."""

    __tablename__ = "players"
    __table_args__ = (
        UniqueConstraint("auction_set", "auction_order", name="uq_players_set_order"),
    )

    player_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    country: Mapped[str] = mapped_column(String(64), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    current_team: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    is_captain: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    auction_set: Mapped[int] = mapped_column(SmallInteger, nullable=False, index=True)
    auction_order: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    base_price_cr: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    is_overseas: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_capped: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    player_status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=PlayerStatus.ACTIVE,
    )

    franchise: Mapped[Optional[Team]] = relationship(
        "Team",
        back_populates="players",
        primaryjoin="foreign(Player.current_team) == Team.short_name",
        viewonly=True,
    )
    retentions: Mapped[list[Retention]] = relationship("Retention", back_populates="player")
    bids: Mapped[list[Bid]] = relationship("Bid", back_populates="player")
    current_auction_sessions: Mapped[list[AuctionState]] = relationship(
        "AuctionState",
        back_populates="current_player",
        foreign_keys="AuctionState.current_player_id",
    )

    @property
    def auction_set_name(self) -> str:
        from app.domain.enums import AUCTION_SET_NAMES

        if 1 <= self.auction_set <= len(AUCTION_SET_NAMES):
            return AUCTION_SET_NAMES[self.auction_set - 1]
        return f"Set {self.auction_set}"

    @property
    def is_free_agent(self) -> bool:
        return self.current_team == "FREE_AGENT"

    def __repr__(self) -> str:
        return f"<Player {self.player_id} {self.name} ({self.role})>"
