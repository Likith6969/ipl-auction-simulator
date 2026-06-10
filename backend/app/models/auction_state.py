from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, SmallInteger, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.database import Base
from app.domain.enums import INITIAL_PURSE_CR, AuctionPhase

if TYPE_CHECKING:
    from app.models.auction_history import AuctionHistory
    from app.models.bid import Bid
    from app.models.player import Player
    from app.models.retention import Retention
    from app.models.team import Team


class AuctionState(Base):
    """Single auction simulation session and its live progress."""

    __tablename__ = "auction_states"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    user_team_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("teams.team_id"),
        nullable=False,
        index=True,
    )
    phase: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default=AuctionPhase.TEAM_SELECT,
    )
    initial_purse_cr: Mapped[Decimal] = mapped_column(
        Numeric(6, 2),
        nullable=False,
        default=Decimal(str(INITIAL_PURSE_CR)),
    )
    current_auction_set: Mapped[Optional[int]] = mapped_column(SmallInteger)
    current_player_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("players.player_id"),
        nullable=True,
    )
    # Per-team runtime state: purse, squad_count, overseas_count, spend breakdown
    team_states: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    # Ordered auction lots with retained players removed from the pool
    auction_pool: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    user_team: Mapped[Team] = relationship(
        "Team",
        back_populates="auction_sessions",
        foreign_keys=[user_team_id],
    )
    current_player: Mapped[Optional[Player]] = relationship(
        "Player",
        back_populates="current_auction_sessions",
        foreign_keys=[current_player_id],
    )
    retentions: Mapped[list[Retention]] = relationship(
        "Retention",
        back_populates="auction_state",
        cascade="all, delete-orphan",
    )
    bids: Mapped[list[Bid]] = relationship(
        "Bid",
        back_populates="auction_state",
        cascade="all, delete-orphan",
    )
    history: Mapped[list[AuctionHistory]] = relationship(
        "AuctionHistory",
        back_populates="auction_state",
        cascade="all, delete-orphan",
        order_by="AuctionHistory.created_at",
    )

    def __repr__(self) -> str:
        return f"<AuctionState {self.id} phase={self.phase}>"
