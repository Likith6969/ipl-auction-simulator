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
