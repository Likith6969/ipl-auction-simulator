from __future__ import annotations

import logging
from decimal import Decimal

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.domain.auction_queue import build_auction_pool, first_pending_lot
from app.domain.enums import AuctionPhase, HistoryEventType
from app.models.auction_history import AuctionHistory
from app.models.auction_state import AuctionState
from app.models.player import Player
from app.models.retention import Retention
from app.models.team import Team
from app.repositories.player_repository import PlayerRepository
from app.repositories.retention_repository import RetentionRepository
from app.repositories.session_repository import SessionRepository
from app.repositories.team_repository import TeamRepository
from app.schemas.auction import AuctionInitializationResult, AuctionPoolStats, TeamPurseState
from app.schemas.retention import RetentionSubmit
from app.services.ai_retention_strategy import AIRetentionStrategy
from app.services.errors import (
    InvalidPhaseError,
    InvalidRetentionError,
    RetentionAlreadyConfirmedError,
    RetentionsIncompleteError,
)
from app.services.session_service import SessionNotFoundError

logger = logging.getLogger(__name__)

RETENTIONS_PER_TEAM = 3


class AuctionInitializationService:
    """Prepare a session for live auction after retentions are finalized."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.session_repo = SessionRepository(db)
        self.team_repo = TeamRepository(db)
        self.player_repo = PlayerRepository(db)
        self.retention_repo = RetentionRepository(db)

    def initialize(
        self,
        session_id: str,
        *,
        user_retentions: RetentionSubmit | None = None,
        force: bool = False,
    ) -> AuctionInitializationResult:
        """
        Complete retentions (user + AI), remove retained players from the pool,
        reconcile team purses, and initialize auction state.

        Idempotent: if the auction is already initialized, returns the current
        snapshot unless ``force`` is True.
        """
        auction_state = self._get_session(session_id)

        if (
            not force
            and auction_state.phase == AuctionPhase.AUCTION
            and auction_state.auction_pool
        ):
            return self._build_result(auction_state, already_initialized=True)

        if auction_state.phase not in {AuctionPhase.RETENTION, AuctionPhase.AUCTION}:
            raise InvalidPhaseError(
                f"Cannot initialize auction while session is in phase {auction_state.phase}."
            )

        user_team = auction_state.user_team
        self._ensure_user_retentions(auction_state, user_team, user_retentions)
        ai_teams_retained = self._ensure_ai_retentions(auction_state)

        self.db.flush()
        if not self._all_teams_retained(auction_state.id):
            raise RetentionsIncompleteError("All franchises must retain exactly 3 players.")

        retained_ids = self.retention_repo.retained_player_ids(auction_state.id)
        self._reconcile_team_purses(auction_state)
        self._initialize_auction_pool(auction_state, retained_ids)

        auction_state.phase = AuctionPhase.AUCTION
        self.db.add(
            AuctionHistory(
                auction_state_id=auction_state.id,
                event_type=HistoryEventType.AUCTION_INITIALIZED,
                payload={
                    "retained_player_ids": sorted(retained_ids),
                    "pool_stats": auction_state.auction_pool.get("stats", {}),
                    "current_auction_set": auction_state.current_auction_set,
                    "current_player_id": auction_state.current_player_id,
                    "ai_teams_retained": ai_teams_retained,
                },
            )
        )
        self.db.commit()
        self.db.refresh(auction_state)

        logger.info(
            "Auction initialized for session %s — pool=%d retained=%d",
            session_id,
            auction_state.auction_pool.get("stats", {}).get("pool_count", 0),
            len(retained_ids),
        )
        return self._build_result(
            auction_state,
            ai_teams_retained=ai_teams_retained,
            already_initialized=False,
        )

    def _ensure_user_retentions(
        self,
        auction_state: AuctionState,
        user_team: Team,
        user_retentions: RetentionSubmit | None,
    ) -> None:
        if self.retention_repo.count_for_team(auction_state.id, user_team.team_id) == RETENTIONS_PER_TEAM:
            return

        if user_retentions is None:
            raise RetentionsIncompleteError(
                "User retentions are required before the auction can be initialized."
            )

        if self.retention_repo.count_for_team(auction_state.id, user_team.team_id) > 0:
            raise RetentionAlreadyConfirmedError(
                "Partial user retentions detected; expected exactly 3 or none."
            )

        self._validate_user_submission(user_retentions, user_team.short_name)
        players_by_id = {
            player.player_id: player
            for player in self.player_repo.get_by_ids(
                [item.player_id for item in user_retentions.retentions]
            )
        }
        assignments: list[tuple[Player, int]] = []
        for item in user_retentions.retentions:
            player = players_by_id.get(item.player_id)
            if player is None:
                raise InvalidRetentionError(f"Player not found: {item.player_id}")
            if player.current_team != user_team.short_name:
                raise InvalidRetentionError(
                    f"Player {player.name} does not belong to {user_team.short_name}."
                )
            assignments.append((player, item.slot))

        retention_rows = self._build_retention_rows(
            auction_state.id,
            user_team.team_id,
            assignments,
        )
        total_cost = sum((row.retention_cost_cr for row in retention_rows), Decimal("0"))
        if total_cost > auction_state.initial_purse_cr:
            raise InvalidRetentionError("Total retention cost exceeds the available purse.")

        self.retention_repo.add_all(retention_rows)
        self.db.add(
            AuctionHistory(
                auction_state_id=auction_state.id,
                event_type=HistoryEventType.RETENTION_CONFIRMED,
                payload={
                    "team_id": user_team.team_id,
                    "team_short_name": user_team.short_name,
                    "is_user_team": True,
                    "retentions": self._retention_payload(retention_rows, assignments),
                    "total_retention_cost_cr": str(total_cost),
                },
            )
        )

    def _ensure_ai_retentions(self, auction_state: AuctionState) -> int:
        ai_teams_retained = 0

        for team in self.team_repo.list_all():
            if team.team_id == auction_state.user_team_id:
                continue
            if self.retention_repo.count_for_team(auction_state.id, team.team_id) == RETENTIONS_PER_TEAM:
                continue

            eligible = self.player_repo.list_by_team_short_name(team.short_name)
            picks = AIRetentionStrategy.pick_retentions(eligible, team.short_name)
            assignments = [(pick.player, pick.slot) for pick in picks]
            retention_rows = self._build_retention_rows(
                auction_state.id,
                team.team_id,
                assignments,
            )

            self.retention_repo.add_all(retention_rows)
            total_cost = sum((row.retention_cost_cr for row in retention_rows), Decimal("0"))
            self.db.add(
                AuctionHistory(
                    auction_state_id=auction_state.id,
                    event_type=HistoryEventType.RETENTION_APPLIED,
                    payload={
                        "team_id": team.team_id,
                        "team_short_name": team.short_name,
                        "is_user_team": False,
                        "retentions": self._retention_payload(retention_rows, assignments),
                        "total_retention_cost_cr": str(total_cost),
                    },
                )
            )
            ai_teams_retained += 1

        return ai_teams_retained

    def _reconcile_team_purses(self, auction_state: AuctionState) -> None:
        """Rebuild purse state for every franchise from retention records."""
        all_retentions = self.retention_repo.list_for_session(auction_state.id)
        by_team: dict[int, list[Retention]] = {}
        for row in all_retentions:
            by_team.setdefault(row.team_id, []).append(row)

        team_states: dict[str, dict[str, str | int]] = {}
        for team in self.team_repo.list_all():
            rows = by_team.get(team.team_id, [])
            total_cost = sum((row.retention_cost_cr for row in rows), Decimal("0"))
            overseas_count = sum(1 for row in rows if row.player.is_overseas)
            team_states[str(team.team_id)] = {
                "purse_remaining_cr": str(auction_state.initial_purse_cr - total_cost),
                "retention_spent_cr": str(total_cost),
                "auction_spent_cr": "0.00",
                "squad_count": len(rows),
                "overseas_count": overseas_count,
            }

        auction_state.team_states = team_states
        flag_modified(auction_state, "team_states")

    def _initialize_auction_pool(
        self,
        auction_state: AuctionState,
        retained_ids: set[int],
    ) -> None:
        active_players = self.player_repo.list_active_ordered()
        auction_state.auction_pool = build_auction_pool(active_players, retained_ids)
        flag_modified(auction_state, "auction_pool")

        first_lot = first_pending_lot(auction_state.auction_pool)
        if first_lot is None:
            auction_state.current_auction_set = None
            auction_state.current_player_id = None
            return

        auction_state.current_auction_set = first_lot["auction_set"]
        auction_state.current_player_id = first_lot["player_id"]

    def _all_teams_retained(self, session_id: str) -> bool:
        return all(
            self.retention_repo.count_for_team(session_id, team.team_id) == RETENTIONS_PER_TEAM
            for team in self.team_repo.list_all()
        )

    def _get_session(self, session_id: str) -> AuctionState:
        auction_state = self.session_repo.get_by_id(session_id)
        if auction_state is None:
            raise SessionNotFoundError(session_id)
        return auction_state

    @staticmethod
    def _validate_user_submission(body: RetentionSubmit, team_short_name: str) -> None:
        slots = [item.slot for item in body.retentions]
        player_ids = [item.player_id for item in body.retentions]

        if len(body.retentions) != RETENTIONS_PER_TEAM:
            raise InvalidRetentionError("Exactly 3 retentions are required.")
        if len(set(slots)) != RETENTIONS_PER_TEAM or set(slots) != {1, 2, 3}:
            raise InvalidRetentionError("Retention slots must be 1, 2, and 3.")
        if len(set(player_ids)) != RETENTIONS_PER_TEAM:
            raise InvalidRetentionError("Each retained player must be unique.")

    @staticmethod
    def _build_retention_rows(
        session_id: str,
        team_id: int,
        assignments: list[tuple[Player, int]],
    ) -> list[Retention]:
        rows: list[Retention] = []
        for player, slot in sorted(assignments, key=lambda item: item[1]):
            rows.append(
                Retention(
                    auction_state_id=session_id,
                    team_id=team_id,
                    player_id=player.player_id,
                    retention_slot=slot,
                    retention_cost_cr=Retention.cost_for_slot(slot),
                )
            )
        return rows

    @staticmethod
    def _retention_payload(
        retention_rows: list[Retention],
        assignments: list[tuple[Player, int]],
    ) -> list[dict]:
        players_by_id = {player.player_id: player for player, _ in assignments}
        return [
            {
                "player_id": row.player_id,
                "player_name": players_by_id[row.player_id].name,
                "slot": row.retention_slot,
                "cost_cr": str(row.retention_cost_cr),
                "is_captain": players_by_id[row.player_id].is_captain,
                "is_capped": players_by_id[row.player_id].is_capped,
            }
            for row in retention_rows
        ]

    def _build_result(
        self,
        auction_state: AuctionState,
        *,
        ai_teams_retained: int = 0,
        already_initialized: bool = False,
    ) -> AuctionInitializationResult:
        retained_ids = sorted(self.retention_repo.retained_player_ids(auction_state.id))
        stats = auction_state.auction_pool.get("stats", {})
        pool_stats = AuctionPoolStats(
            total_active_players=int(stats.get("total_active_players", 0)),
            retained_count=int(stats.get("retained_count", len(retained_ids))),
            pool_count=int(stats.get("pool_count", 0)),
        )

        team_purses: list[TeamPurseState] = []
        for team in self.team_repo.list_all():
            state = auction_state.team_states.get(str(team.team_id), {})
            team_purses.append(
                TeamPurseState(
                    team_id=team.team_id,
                    short_name=team.short_name,
                    purse_remaining_cr=Decimal(str(state.get("purse_remaining_cr", "0"))),
                    retention_spent_cr=Decimal(str(state.get("retention_spent_cr", "0"))),
                    auction_spent_cr=Decimal(str(state.get("auction_spent_cr", "0"))),
                    squad_count=int(state.get("squad_count", 0)),
                    overseas_count=int(state.get("overseas_count", 0)),
                )
            )

        return AuctionInitializationResult(
            session_id=auction_state.id,
            phase=auction_state.phase,
            user_retentions_complete=self.retention_repo.count_for_team(
                auction_state.id,
                auction_state.user_team_id,
            )
            == RETENTIONS_PER_TEAM,
            ai_teams_retained=ai_teams_retained,
            all_retentions_complete=self._all_teams_retained(auction_state.id),
            retained_player_ids=retained_ids,
            pool_stats=pool_stats,
            current_auction_set=auction_state.current_auction_set,
            current_player_id=auction_state.current_player_id,
            team_purses=team_purses,
            already_initialized=already_initialized,
        )
