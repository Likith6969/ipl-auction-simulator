from decimal import Decimal

from sqlalchemy.orm import Session

from app.domain.enums import INITIAL_PURSE_CR, AuctionPhase, HistoryEventType
from app.models.auction_history import AuctionHistory
from app.models.auction_state import AuctionState
from app.repositories.session_repository import SessionRepository
from app.repositories.team_repository import TeamRepository


class TeamNotFoundError(Exception):
    def __init__(self, team_id: int) -> None:
        self.team_id = team_id
        super().__init__(f"Team not found: {team_id}")


class SessionNotFoundError(Exception):
    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        super().__init__(f"Session not found: {session_id}")


class SessionService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.team_repo = TeamRepository(db)
        self.session_repo = SessionRepository(db)

    def list_teams(self):
        return self.team_repo.list_all()

    def create_session(self, user_team_id: int) -> AuctionState:
        team = self.team_repo.get_by_id(user_team_id)
        if team is None:
            raise TeamNotFoundError(user_team_id)

        teams = self.team_repo.list_all()
        team_states = {
            str(t.team_id): {
                "purse_remaining_cr": str(INITIAL_PURSE_CR),
                "retention_spent_cr": "0.00",
                "auction_spent_cr": "0.00",
                "squad_count": 0,
                "overseas_count": 0,
            }
            for t in teams
        }

        auction_state = AuctionState(
            user_team_id=user_team_id,
            phase=AuctionPhase.RETENTION,
            initial_purse_cr=Decimal(str(INITIAL_PURSE_CR)),
            team_states=team_states,
        )
        self.session_repo.create(auction_state)

        history = AuctionHistory(
            auction_state_id=auction_state.id,
            event_type=HistoryEventType.SESSION_CREATED,
            payload={
                "user_team_id": team.team_id,
                "user_team_name": team.team_name,
                "user_team_short_name": team.short_name,
                "phase": AuctionPhase.RETENTION,
            },
        )
        self.db.add(history)
        self.db.commit()
        self.db.refresh(auction_state)

        # Eager-load user_team for response serialization
        loaded = self.session_repo.get_by_id(auction_state.id)
        assert loaded is not None
        return loaded

    def get_session(self, session_id: str) -> AuctionState:
        session = self.session_repo.get_by_id(session_id)
        if session is None:
            raise SessionNotFoundError(session_id)
        return session
