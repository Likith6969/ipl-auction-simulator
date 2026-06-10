from decimal import Decimal

from pydantic import BaseModel, Field


class TeamPurseState(BaseModel):
    team_id: int
    short_name: str
    purse_remaining_cr: Decimal
    retention_spent_cr: Decimal
    auction_spent_cr: Decimal
    squad_count: int
    overseas_count: int


class AuctionPoolStats(BaseModel):
    total_active_players: int
    retained_count: int
    pool_count: int


class AuctionInitializationResult(BaseModel):
    session_id: str
    phase: str
    user_retentions_complete: bool
    ai_teams_retained: int
    all_retentions_complete: bool
    retained_player_ids: list[int]
    pool_stats: AuctionPoolStats
    current_auction_set: int | None
    current_player_id: int | None
    team_purses: list[TeamPurseState]
    already_initialized: bool = False
