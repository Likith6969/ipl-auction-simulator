from decimal import Decimal

from app.models.player import Player
from app.services.ai_retention_strategy import AIRetentionStrategy


def _player(
    player_id: int,
    *,
    is_captain: bool = False,
    is_capped: bool = True,
    auction_set: int = 2,
    base_price_cr: str = "1.0",
) -> Player:
    return Player(
        player_id=player_id,
        name=f"Player {player_id}",
        country="India",
        role="BATTER",
        current_team="MI",
        is_captain=is_captain,
        auction_set=auction_set,
        auction_order=player_id,
        base_price_cr=Decimal(base_price_cr),
        is_overseas=False,
        is_capped=is_capped,
        player_status="active",
    )


def test_captain_ranked_first() -> None:
    players = [
        _player(1, is_capped=True, auction_set=1, base_price_cr="2.0"),
        _player(2, is_captain=True, is_capped=True, auction_set=2, base_price_cr="1.0"),
        _player(3, is_capped=False, auction_set=6, base_price_cr="0.2"),
    ]
    picks = AIRetentionStrategy.pick_retentions(players, "MI")
    assert picks[0].player.player_id == 2
    assert picks[0].slot == 1


def test_capped_before_uncapped() -> None:
    players = [
        _player(1, is_capped=False, auction_set=6),
        _player(2, is_capped=True, auction_set=3),
        _player(3, is_capped=True, auction_set=2),
        _player(4, is_capped=False, auction_set=6),
    ]
    ranked = AIRetentionStrategy.rank_players(players)
    assert [player.player_id for player in ranked[:2]] == [3, 2]


def test_deterministic_ordering() -> None:
    players = [
        _player(10, auction_set=2, base_price_cr="0.75"),
        _player(11, auction_set=2, base_price_cr="1.5"),
        _player(12, auction_set=1, base_price_cr="2.0"),
        _player(13, auction_set=3, base_price_cr="1.0"),
    ]
    first = AIRetentionStrategy.rank_players(players)
    second = AIRetentionStrategy.rank_players(list(reversed(players)))
    assert [player.player_id for player in first] == [player.player_id for player in second]
