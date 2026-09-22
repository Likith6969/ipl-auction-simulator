from enum import StrEnum


class PlayerRole(StrEnum):
    BATTER = "BATTER"
    BOWLER = "BOWLER"
    ALLROUNDER = "ALLROUNDER"
    WK_BATTER = "WK_BATTER"


class PlayerStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class AuctionPhase(StrEnum):
    TEAM_SELECT = "TEAM_SELECT"
    RETENTION = "RETENTION"
    AUCTION = "AUCTION"
    COMPLETED = "COMPLETED"


class LotStatus(StrEnum):
    PENDING = "PENDING"
    LIVE = "LIVE"
    SOLD = "SOLD"
    UNSOLD = "UNSOLD"
    SKIPPED_RETAINED = "SKIPPED_RETAINED"


class HistoryEventType(StrEnum):
    SESSION_CREATED = "SESSION_CREATED"
    RETENTION_APPLIED = "RETENTION_APPLIED"
    RETENTION_CONFIRMED = "RETENTION_CONFIRMED"
    AUCTION_INITIALIZED = "AUCTION_INITIALIZED"
    SET_STARTED = "SET_STARTED"
    LOT_OPENED = "LOT_OPENED"
    BID_PLACED = "BID_PLACED"
    BID_PASSED = "BID_PASSED"
    LOT_SOLD = "LOT_SOLD"
    LOT_UNSOLD = "LOT_UNSOLD"
    SET_COMPLETED = "SET_COMPLETED"
    AUCTION_COMPLETED = "AUCTION_COMPLETED"


# auction_config.json auction_order index (0-based) + 1 == players.auction_set
AUCTION_SET_NAMES: tuple[str, ...] = (
    "Marquee Set",
    "Capped Batsmen",
    "Capped Bowlers",
    "Capped All-Rounders",
    "Capped Wicket Keepers",
    "Uncapped Players",
    "Overseas Players",
    "Accelerated Auction",
)

# auction_config.json retentions slot -> cost (Cr)
RETENTION_COSTS: dict[int, float] = {1: 18.0, 2: 15.0, 3: 8.0}

INITIAL_PURSE_CR = 120.0
MAX_SQUAD_SIZE = 25
MIN_SQUAD_SIZE = 18
MAX_OVERSEAS_PLAYERS = 8


# ---------------------------------------------------------------------------
# Auction State Machine — run states
# ---------------------------------------------------------------------------


class PublicRunState(StrEnum):
    """States exposed to the frontend via the live_state snapshot.

    These are the ONLY normal auction run states the UI should ever see.
    Internal engine states must never appear here.
    """

    READY = "READY"
    SET_INTRO = "SET_INTRO"
    LOT_OPEN = "LOT_OPEN"
    BIDDING_ACTIVE = "BIDDING_ACTIVE"
    COUNTDOWN = "COUNTDOWN"
    GOING_ONCE = "GOING_ONCE"
    GOING_TWICE = "GOING_TWICE"
    FINAL_CALL = "FINAL_CALL"
    RTM_PENDING = "RTM_PENDING"
    PAUSED = "PAUSED"
    AUCTION_COMPLETE = "AUCTION_COMPLETE"


class InternalRunState(StrEnum):
    """Engine-only transition states.

    These MUST NOT appear as ``public_run_state`` values in any API response.
    When the engine is in one of these states it sets ``is_transitioning=True``
    and exposes the most recent public state to the frontend.
    """

    LOT_RESOLVING = "LOT_RESOLVING"
    BETWEEN_LOTS = "BETWEEN_LOTS"
    AUCTION_ENDING = "AUCTION_ENDING"


class AuctionEvent(StrEnum):
    """Events that drive the auction state machine transitions."""

    START_AUCTION = "start_auction"
    OPEN_LOT = "open_lot"
    FIRST_BID = "first_bid"
    SKIP_UNSOLD = "skip_unsold"
    BID_OR_TICK = "bid_or_tick"
    NEW_BID = "new_bid"
    TIMER_EXPIRED = "timer_expired"
    HAMMER_AND_RTM_ELIGIBLE = "hammer_and_rtm_eligible"
    HAMMER_SOLD = "hammer_sold"
    RTM_RESOLVED = "rtm_resolved"
    NEXT_SET = "next_set"
    POOL_EXHAUSTED = "pool_exhausted"
    PAUSE = "pause"
    RESUME = "resume"


class SpeedProfile(StrEnum):
    """Controls auction pacing; accelerated mode is a flag, not a separate state."""

    NORMAL = "normal"
    FAST = "fast"
    VERY_FAST = "very_fast"


# Sentinel: bumped whenever the live_state JSON shape changes incompatibly.
LIVE_STATE_VERSION: int = 1
