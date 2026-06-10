from __future__ import annotations

import csv
import logging
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import TEAMS_CSV, resolve_players_csv
from app.domain.enums import PlayerRole, PlayerStatus
from app.models.player import Player
from app.models.team import Team

logger = logging.getLogger(__name__)

VALID_ROLES = frozenset(role.value for role in PlayerRole)
VALID_PLAYER_STATUSES = frozenset(status.value for status in PlayerStatus)
FREE_AGENT = "FREE_AGENT"


@dataclass
class SeedStats:
    teams_inserted: int = 0
    teams_updated: int = 0
    players_inserted: int = 0
    players_updated: int = 0
    skipped_entirely: bool = False

    @property
    def teams_processed(self) -> int:
        return self.teams_inserted + self.teams_updated

    @property
    def players_processed(self) -> int:
        return self.players_inserted + self.players_updated


@dataclass
class _SeedContext:
    team_short_names: set[str] = field(default_factory=set)
    existing_team_ids: set[int] = field(default_factory=set)
    existing_player_ids: set[int] = field(default_factory=set)


class SeedDataError(Exception):
    """Raised when CSV data fails validation."""


def is_database_seeded(session: Session) -> bool:
    """Return True when reference teams and players are already loaded."""
    team_count = session.scalar(select(func.count()).select_from(Team)) or 0
    player_count = session.scalar(select(func.count()).select_from(Player)) or 0
    return team_count > 0 and player_count > 0


def seed_reference_data(session: Session, *, force: bool = False) -> SeedStats:
    """
    Load teams and players from CSV into SQLite.

    Idempotent: existing rows are merged by primary key (no duplicate inserts).
    When the database is already seeded and ``force`` is False, returns immediately.
    """
    if not force and is_database_seeded(session):
        team_count = session.scalar(select(func.count()).select_from(Team)) or 0
        player_count = session.scalar(select(func.count()).select_from(Player)) or 0
        logger.info(
            "Database already seeded (%d teams, %d players). Skipping import.",
            team_count,
            player_count,
        )
        return SeedStats(skipped_entirely=True)

    context = _load_existing_keys(session)
    stats = SeedStats()

    stats = _seed_teams(session, TEAMS_CSV, context, stats)
    stats = _seed_players(session, resolve_players_csv(), context, stats)

    session.commit()
    logger.info(
        "Seed complete — teams: %d inserted, %d updated | players: %d inserted, %d updated",
        stats.teams_inserted,
        stats.teams_updated,
        stats.players_inserted,
        stats.players_updated,
    )
    return stats


def _load_existing_keys(session: Session) -> _SeedContext:
    context = _SeedContext()
    context.existing_team_ids = set(session.scalars(select(Team.team_id)).all())
    context.existing_player_ids = set(session.scalars(select(Player.player_id)).all())
    context.team_short_names = set(session.scalars(select(Team.short_name)).all())
    return context


def _seed_teams(
    session: Session,
    csv_path: Path,
    context: _SeedContext,
    stats: SeedStats,
) -> SeedStats:
    rows = _read_csv(csv_path)
    _validate_headers(rows, {"team_id", "team_name", "short_name"}, csv_path.name)

    for row in rows:
        team = Team(
            team_id=_parse_int(row["team_id"], "team_id", csv_path.name),
            team_name=row["team_name"].strip(),
            short_name=row["short_name"].strip(),
        )
        if not team.team_name:
            raise SeedDataError(f"{csv_path.name}: team_name cannot be empty (id={team.team_id})")
        if not team.short_name:
            raise SeedDataError(f"{csv_path.name}: short_name cannot be empty (id={team.team_id})")

        if team.team_id in context.existing_team_ids:
            session.merge(team)
            stats.teams_updated += 1
        else:
            session.add(team)
            context.existing_team_ids.add(team.team_id)
            stats.teams_inserted += 1

        context.team_short_names.add(team.short_name)

    return stats


def _seed_players(
    session: Session,
    csv_path: Path,
    context: _SeedContext,
    stats: SeedStats,
) -> SeedStats:
    if not context.team_short_names:
        raise SeedDataError("Teams must be seeded before players.")

    rows = _read_csv(csv_path)
    _validate_headers(
        rows,
        {
            "id",
            "name",
            "country",
            "role",
            "current_team",
            "is_captain",
            "auction_set",
            "auction_order",
            "base_price_cr",
            "is_overseas",
            "is_capped",
            "player_status",
        },
        csv_path.name,
    )

    valid_teams = context.team_short_names | {FREE_AGENT}
    seen_set_orders: set[tuple[int, int]] = set()

    for row in rows:
        player_id = _parse_int(row["id"], "id", csv_path.name)
        current_team = row["current_team"].strip()
        auction_set = _parse_int(row["auction_set"], "auction_set", csv_path.name)
        auction_order = _parse_int(row["auction_order"], "auction_order", csv_path.name)
        role = row["role"].strip()

        if role not in VALID_ROLES:
            raise SeedDataError(
                f"{csv_path.name}: invalid role '{role}' for player id={player_id}"
            )
        if current_team not in valid_teams:
            raise SeedDataError(
                f"{csv_path.name}: unknown current_team '{current_team}' for player id={player_id}"
            )

        set_order_key = (auction_set, auction_order)
        if set_order_key in seen_set_orders:
            raise SeedDataError(
                f"{csv_path.name}: duplicate auction_set/auction_order "
                f"({auction_set}, {auction_order})"
            )
        seen_set_orders.add(set_order_key)

        player_status = row["player_status"].strip().lower()
        if player_status not in VALID_PLAYER_STATUSES:
            raise SeedDataError(
                f"{csv_path.name}: invalid player_status '{player_status}' for id={player_id}"
            )

        player = Player(
            player_id=player_id,
            name=row["name"].strip(),
            country=row["country"].strip(),
            role=role,
            current_team=current_team,
            is_captain=_parse_bool(row["is_captain"]),
            auction_set=auction_set,
            auction_order=auction_order,
            base_price_cr=_parse_decimal(row["base_price_cr"], "base_price_cr", csv_path.name),
            is_overseas=_parse_bool(row["is_overseas"]),
            is_capped=_parse_bool(row["is_capped"]),
            player_status=player_status,
        )

        if not player.name:
            raise SeedDataError(f"{csv_path.name}: name cannot be empty (id={player_id})")

        if player.player_id in context.existing_player_ids:
            session.merge(player)
            stats.players_updated += 1
        else:
            session.add(player)
            context.existing_player_ids.add(player.player_id)
            stats.players_inserted += 1

    return stats


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f"CSV file not found: {path}")

    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise SeedDataError(f"{path.name}: CSV has no header row")
        return [dict(row) for row in reader]


def _validate_headers(
    rows: list[dict[str, str]],
    required: set[str],
    filename: str,
) -> None:
    if not rows:
        raise SeedDataError(f"{filename}: CSV contains no data rows")

    headers = set(rows[0].keys())
    missing = required - headers
    if missing:
        raise SeedDataError(f"{filename}: missing required columns: {sorted(missing)}")


def _parse_int(value: str, field_name: str, filename: str) -> int:
    try:
        return int(value.strip())
    except (ValueError, AttributeError) as exc:
        raise SeedDataError(f"{filename}: invalid integer for {field_name}: {value!r}") from exc


def _parse_decimal(value: str, field_name: str, filename: str) -> Decimal:
    try:
        return Decimal(value.strip())
    except (InvalidOperation, AttributeError) as exc:
        raise SeedDataError(f"{filename}: invalid decimal for {field_name}: {value!r}") from exc


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    raise SeedDataError(f"invalid boolean value: {value!r}")
