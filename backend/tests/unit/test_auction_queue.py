from decimal import Decimal

from app.domain.auction_queue import build_auction_pool
from app.models.player import Player


def _player(player_id: int, auction_set: int, auction_order: int) -> Player:
    return Player(
        player_id=player_id,
        name=f"P{player_id}",
        country="India",
        role="BATTER",
        current_team="MI",
        is_captain=False,
        auction_set=auction_set,
        auction_order=auction_order,
        base_price_cr=Decimal("1.0"),
        is_overseas=False,
        is_capped=True,
        player_status="active",
    )


def test_build_auction_pool_excludes_retained_players() -> None:
    players = [_player(1, 1, 1), _player(2, 1, 2), _player(3, 1, 3)]
    pool = build_auction_pool(players, {2})

    assert pool["stats"]["retained_count"] == 1
    assert pool["stats"]["pool_count"] == 2
    assert [lot["player_id"] for lot in pool["lots"]] == [1, 3]


def test_build_auction_pool_preserves_order() -> None:
    players = [_player(3, 2, 1), _player(1, 1, 1), _player(2, 1, 2)]
    ordered = sorted(players, key=lambda p: (p.auction_set, p.auction_order))
    pool = build_auction_pool(ordered, set())

    assert [lot["player_id"] for lot in pool["lots"]] == [1, 2, 3]
