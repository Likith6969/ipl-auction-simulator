from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"
DATABASE_DIR = BASE_DIR / "data"
DATABASE_PATH = DATABASE_DIR / "ipl_auction.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH.as_posix()}"

TEAMS_CSV = DATA_DIR / "teams.csv"
PLAYERS_CSV = DATA_DIR / "players.csv"
PLAYERS_CSV_FALLBACK = DATA_DIR / "players_data_set(ipl).csv"
AUCTION_CONFIG_JSON = DATA_DIR / "auction_config.json"


def resolve_players_csv() -> Path:
    """Prefer players.csv; fall back to the bundled dataset filename."""
    if PLAYERS_CSV.is_file():
        return PLAYERS_CSV
    if PLAYERS_CSV_FALLBACK.is_file():
        return PLAYERS_CSV_FALLBACK
    raise FileNotFoundError(
        f"No player CSV found. Expected {PLAYERS_CSV} or {PLAYERS_CSV_FALLBACK}."
    )
