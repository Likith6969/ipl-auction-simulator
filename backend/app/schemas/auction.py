from decimal import Decimal
from typing import Any

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


# ---------------------------------------------------------------------------
# State-machine schemas
# ---------------------------------------------------------------------------


class LiveStatePauseInfo(BaseModel):
    active: bool
    paused_from: str | None = None


class LiveStateCountdownInfo(BaseModel):
    phase: str | None = None      # "countdown" | "going_once" | … | None
    expires_at: str | None = None  # ISO-8601 UTC or None
    generation: int = 0


class LiveStateRtmWindowInfo(BaseModel):
    active: bool
    expires_at: str | None = None


class LiveStateRead(BaseModel):
    """Validated representation of the live_state JSON column.

    This is the lightweight runtime state exposed to the frontend.
    It does NOT contain player data, purse figures, bid amounts, or
    squad counts — those belong in CurrentLotSnapshot / TeamPurseState.
    """

    version: int
    public_run_state: str          # A PublicRunState value
    speed_profile: str             # A SpeedProfile value
    is_accelerated: bool
    pause: LiveStatePauseInfo
    countdown: LiveStateCountdownInfo
    rtm_window: LiveStateRtmWindowInfo
    internal_phase: str | None = None   # An InternalRunState value, or None
    timing_ms: dict[str, int]

    model_config = {"from_attributes": True}


class CurrentLotSnapshot(BaseModel):
    """Current lot's bid-tracking state, derived from auction_pool.lots[current_lot_index].

    Persistent fields (player identity, set name, base price) come from the
    pool lot dict.  Live bid fields (current_bid_cr, leading_team_id, bid_count)
    are populated by BiddingService when the lot is LIVE; they remain null/0
    while the lot is still PENDING or LOT_OPEN with no bids.
    """

    lot_index: int
    player_id: int
    player_name: str
    auction_set: int
    set_name: str
    base_price_cr: Decimal
    is_overseas: bool
    status: str                         # A LotStatus value

    # Bid tracking — null/0 until BiddingService starts writing to the lot
    current_bid_cr: Decimal | None = None
    leading_team_id: int | None = None
    bid_count: int = 0


class AuctionSnapshot(BaseModel):
    """Full auction-engine state snapshot returned by GET /sessions/{id}/auction/state.

    Combines the lightweight live_state with derived context (current lot,
    team purses) so the frontend has everything it needs in a single response.
    """

    session_id: str
    phase: str                          # AuctionPhase value
    current_auction_set: int | None
    current_player_id: int | None
    live_state: LiveStateRead
    current_lot: CurrentLotSnapshot | None
    team_purses: list[TeamPurseState]

