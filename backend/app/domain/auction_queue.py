from __future__ import annotations

from typing import Any

from app.domain.enums import AUCTION_SET_NAMES, LotStatus
from app.models.player import Player

AUCTION_POOL_VERSION = 1


def auction_set_name(set_number: int) -> str:
    if 1 <= set_number <= len(AUCTION_SET_NAMES):
        return AUCTION_SET_NAMES[set_number - 1]
    return f"Set {set_number}"


def build_auction_pool(
    ordered_players: list[Player],
    retained_player_ids: set[int],
) -> dict[str, Any]:
    """
    Build the session auction pool excluding retained players.

    Players must already be ordered by ``auction_set ASC, auction_order ASC``.
    Retained players are removed from the pool entirely (not random).
    """
    lots: list[dict[str, Any]] = []

    for player in ordered_players:
        if player.player_id in retained_player_ids:
            continue
        lots.append(
            {
                "player_id": player.player_id,
                "player_name": player.name,
                "role": player.role,
                "auction_set": player.auction_set,
                "auction_order": player.auction_order,
                "set_name": auction_set_name(player.auction_set),
                "base_price_cr": str(player.base_price_cr),
                "is_overseas": player.is_overseas,
                "status": LotStatus.PENDING,
            }
        )

    return {
        "version": AUCTION_POOL_VERSION,
        "retained_player_ids": sorted(retained_player_ids),
        "lots": lots,
        "current_lot_index": 0,
        "stats": {
            "total_active_players": len(ordered_players),
            "retained_count": len(retained_player_ids),
            "pool_count": len(lots),
        },
    }


def first_pending_lot(auction_pool: dict[str, Any]) -> dict[str, Any] | None:
    lots = auction_pool.get("lots", [])
    index = auction_pool.get("current_lot_index", 0)
    if 0 <= index < len(lots):
        return lots[index]
    return lots[0] if lots else None
