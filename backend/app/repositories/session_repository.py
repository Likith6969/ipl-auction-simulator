from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.auction_state import AuctionState


class SessionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, auction_state: AuctionState) -> AuctionState:
        self.db.add(auction_state)
        self.db.flush()
        return auction_state

    def get_by_id(self, session_id: str) -> AuctionState | None:
        stmt = (
            select(AuctionState)
            .options(joinedload(AuctionState.user_team))
            .where(AuctionState.id == session_id)
        )
        return self.db.scalar(stmt)
