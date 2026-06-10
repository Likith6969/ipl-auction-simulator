from __future__ import annotations

from dataclasses import dataclass

from app.models.player import Player


class InsufficientEligiblePlayersError(Exception):
    def __init__(self, team_short_name: str, available: int) -> None:
        self.team_short_name = team_short_name
        self.available = available
        super().__init__(
            f"Team {team_short_name} has only {available} eligible players; 3 required."
        )


@dataclass(frozen=True)
class RetentionPick:
    player: Player
    slot: int


class AIRetentionStrategy:
    """
    Deterministic AI retention ranking (never random).

    Priority:
      1. Captain
      2. Capped players
      3. Core squad players (marquee / early auction sets, then base price)
    """

    @staticmethod
    def rank_players(players: list[Player]) -> list[Player]:
        return sorted(
            players,
            key=lambda player: (
                0 if player.is_captain else 1,
                0 if player.is_capped else 1,
                player.auction_set,
                player.auction_order,
                -float(player.base_price_cr),
                player.player_id,
            ),
        )

    @classmethod
    def pick_retentions(cls, players: list[Player], team_short_name: str) -> list[RetentionPick]:
        ranked = cls.rank_players(players)
        if len(ranked) < 3:
            raise InsufficientEligiblePlayersError(team_short_name, len(ranked))

        return [
            RetentionPick(player=player, slot=slot)
            for slot, player in enumerate(ranked[:3], start=1)
        ]
