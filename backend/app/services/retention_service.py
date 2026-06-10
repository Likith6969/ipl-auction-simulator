from decimal import Decimal

from sqlalchemy.orm import Session

from app.domain.enums import RETENTION_COSTS
from app.repositories.player_repository import PlayerRepository
from app.repositories.retention_repository import RetentionRepository
from app.repositories.session_repository import SessionRepository
from app.repositories.team_repository import TeamRepository
from app.schemas.retention import (
    AllRetentionsView,
    RetentionConfirmResponse,
    RetentionItemRead,
    RetentionPlayerRead,
    RetentionSlotCost,
    RetentionSubmit,
    RetentionSummary,
    RetentionView,
    TeamRetentionSummary,
)
from app.services.auction_initialization_service import AuctionInitializationService
from app.services.errors import (
    InvalidPhaseError,
    InvalidRetentionError,
    RetentionAlreadyConfirmedError,
    RetentionsIncompleteError,
)
from app.services.session_service import SessionNotFoundError

# Re-export for API modules that import from retention_service.
__all__ = [
    "InvalidPhaseError",
    "RetentionAlreadyConfirmedError",
    "InvalidRetentionError",
    "RetentionService",
]


class RetentionService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.session_repo = SessionRepository(db)
        self.team_repo = TeamRepository(db)
        self.player_repo = PlayerRepository(db)
        self.retention_repo = RetentionRepository(db)
        self.init_service = AuctionInitializationService(db)

    def get_retention_view(self, session_id: str) -> RetentionView:
        auction_state = self.session_repo.get_by_id(session_id)
        if auction_state is None:
            raise SessionNotFoundError(session_id)

        team = auction_state.user_team
        eligible_players = self.player_repo.list_by_team_short_name(team.short_name)
        existing = self.retention_repo.list_for_team(session_id, team.team_id)
        is_confirmed = len(existing) == 3

        selected = [self._to_retention_item_read(row) for row in existing]
        summary = self._build_summary(auction_state.initial_purse_cr, selected)

        return RetentionView(
            session_id=auction_state.id,
            team_id=team.team_id,
            team_name=team.team_name,
            short_name=team.short_name,
            phase=auction_state.phase,
            retention_costs=self._slot_costs(),
            eligible_players=[
                RetentionPlayerRead.model_validate(player) for player in eligible_players
            ],
            selected_retentions=selected,
            summary=summary,
            is_confirmed=is_confirmed,
        )

    def get_all_retentions(self, session_id: str) -> AllRetentionsView:
        auction_state = self.session_repo.get_by_id(session_id)
        if auction_state is None:
            raise SessionNotFoundError(session_id)

        all_rows = self.retention_repo.list_for_session(session_id)
        by_team: dict[int, list] = {}
        for row in all_rows:
            by_team.setdefault(row.team_id, []).append(row)

        teams_summary: list[TeamRetentionSummary] = []
        for team in self.team_repo.list_all():
            team_rows = by_team.get(team.team_id, [])
            items = [self._to_retention_item_read(row) for row in team_rows]
            teams_summary.append(
                TeamRetentionSummary(
                    team_id=team.team_id,
                    team_name=team.team_name,
                    short_name=team.short_name,
                    is_user_team=team.team_id == auction_state.user_team_id,
                    retentions=items,
                    summary=self._build_summary(auction_state.initial_purse_cr, items),
                    is_confirmed=len(items) == 3,
                )
            )

        all_complete = all(team.is_confirmed for team in teams_summary)
        return AllRetentionsView(
            session_id=auction_state.id,
            phase=auction_state.phase,
            teams=teams_summary,
            all_retentions_complete=all_complete,
        )

    def submit_user_retentions(
        self,
        session_id: str,
        body: RetentionSubmit,
    ) -> RetentionConfirmResponse:
        try:
            init_result = self.init_service.initialize(session_id, user_retentions=body)
        except RetentionsIncompleteError as exc:
            raise InvalidRetentionError(str(exc)) from exc

        auction_state = self.session_repo.get_by_id(session_id)
        if auction_state is None:
            raise SessionNotFoundError(session_id)

        user_rows = self.retention_repo.list_for_team(session_id, auction_state.user_team_id)
        selected = [self._to_retention_item_read(row) for row in user_rows]
        summary = self._build_summary(auction_state.initial_purse_cr, selected)

        return RetentionConfirmResponse(
            session_id=init_result.session_id,
            phase=init_result.phase,
            retentions=selected,
            summary=summary,
            ai_teams_retained=init_result.ai_teams_retained,
            all_retentions_complete=init_result.all_retentions_complete,
        )

    @staticmethod
    def _slot_costs() -> list[RetentionSlotCost]:
        return [
            RetentionSlotCost(slot=slot, cost_cr=Decimal(str(cost)))
            for slot, cost in sorted(RETENTION_COSTS.items())
        ]

    @staticmethod
    def _build_summary(
        initial_purse_cr: Decimal,
        selected: list[RetentionItemRead],
    ) -> RetentionSummary:
        total = sum((item.retention_cost_cr for item in selected), Decimal("0"))
        return RetentionSummary(
            initial_purse_cr=initial_purse_cr,
            total_retention_cost_cr=total,
            remaining_purse_cr=initial_purse_cr - total,
            slots_selected=len(selected),
        )

    @staticmethod
    def _to_retention_item_read(retention) -> RetentionItemRead:
        return RetentionItemRead(
            player_id=retention.player_id,
            retention_slot=retention.retention_slot,
            retention_cost_cr=retention.retention_cost_cr,
            player=RetentionPlayerRead.model_validate(retention.player),
        )
