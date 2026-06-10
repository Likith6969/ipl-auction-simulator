from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.retention import Retention


class RetentionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_for_team(self, session_id: str, team_id: int) -> list[Retention]:
        stmt = (
            select(Retention)
            .options(joinedload(Retention.player))
            .where(
                Retention.auction_state_id == session_id,
                Retention.team_id == team_id,
            )
            .order_by(Retention.retention_slot.asc())
        )
        return list(self.db.scalars(stmt).unique().all())

    def list_for_session(self, session_id: str) -> list[Retention]:
        stmt = (
            select(Retention)
            .options(joinedload(Retention.player), joinedload(Retention.team))
            .where(Retention.auction_state_id == session_id)
            .order_by(Retention.team_id.asc(), Retention.retention_slot.asc())
        )
        return list(self.db.scalars(stmt).unique().all())

    def retained_player_ids(self, session_id: str) -> set[int]:
        stmt = select(Retention.player_id).where(Retention.auction_state_id == session_id)
        return set(self.db.scalars(stmt).all())

    def count_for_team(self, session_id: str, team_id: int) -> int:
        stmt = select(Retention).where(
            Retention.auction_state_id == session_id,
            Retention.team_id == team_id,
        )
        return len(list(self.db.scalars(stmt).all()))

    def add_all(self, retentions: list[Retention]) -> None:
        self.db.add_all(retentions)
