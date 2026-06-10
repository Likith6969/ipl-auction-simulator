from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.player import Player
from app.domain.enums import PlayerStatus


class PlayerRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_by_team_short_name(self, short_name: str) -> list[Player]:
        stmt = (
            select(Player)
            .where(
                Player.current_team == short_name,
                Player.player_status == PlayerStatus.ACTIVE,
            )
            .order_by(Player.is_captain.desc(), Player.name.asc())
        )
        return list(self.db.scalars(stmt).all())

    def list_active_ordered(self) -> list[Player]:
        stmt = (
            select(Player)
            .where(Player.player_status == PlayerStatus.ACTIVE)
            .order_by(Player.auction_set.asc(), Player.auction_order.asc())
        )
        return list(self.db.scalars(stmt).all())

    def get_by_ids(self, player_ids: list[int]) -> list[Player]:
        if not player_ids:
            return []
        stmt = select(Player).where(Player.player_id.in_(player_ids))
        players = list(self.db.scalars(stmt).all())
        by_id = {player.player_id: player for player in players}
        return [by_id[player_id] for player_id in player_ids if player_id in by_id]
