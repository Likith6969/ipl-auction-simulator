from collections.abc import Generator
import logging

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import DATABASE_DIR, DATABASE_URL

logger = logging.getLogger(__name__)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def create_tables() -> None:
    """Create all tables defined by SQLAlchemy models."""
    import app.models  # noqa: F401 — register model metadata

    DATABASE_DIR.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    _apply_sqlite_migrations()
    logger.info("Database tables ensured at %s", DATABASE_DIR)


def _apply_sqlite_migrations() -> None:
    """Lightweight SQLite migrations for additive schema changes."""
    if not DATABASE_URL.startswith("sqlite"):
        return

    inspector = inspect(engine)
    if not inspector.has_table("auction_states"):
        return

    columns = {column["name"] for column in inspector.get_columns("auction_states")}
    if "auction_pool" not in columns:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE auction_states "
                    "ADD COLUMN auction_pool JSON NOT NULL DEFAULT '{}'"
                )
            )
        logger.info("Applied migration: auction_states.auction_pool")


def init_db(*, seed: bool = True, force_seed: bool = False) -> None:
    """
    Initialize the SQLite database: create schema and load reference CSV data.

    Seeding is idempotent — duplicate imports are prevented via primary-key merge
    and an early exit when data is already present (unless ``force_seed`` is True).
    """
    create_tables()

    if not seed:
        return

    from app.services.seed_loader import seed_reference_data

    with SessionLocal() as session:
        stats = seed_reference_data(session, force=force_seed)

    if stats.skipped_entirely:
        logger.info("Reference data import skipped (already seeded).")
    else:
        logger.info(
            "Reference data loaded — teams: +%d / ~%d updated, players: +%d / ~%d updated",
            stats.teams_inserted,
            stats.teams_updated,
            stats.players_inserted,
            stats.players_updated,
        )


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
