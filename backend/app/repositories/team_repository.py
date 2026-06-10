from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.team import Team


class TeamRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_all(self) -> list[Team]:
        return list(
            self.db.scalars(select(Team).order_by(Team.team_id)).all()
        )

    def get_by_id(self, team_id: int) -> Team | None:
        return self.db.get(Team, team_id)
