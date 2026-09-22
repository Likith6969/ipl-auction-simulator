"""
Integration tests for the auction state machine foundation.

Tests the full HTTP flow through the new endpoints:
    POST /sessions/{id}/auction/start      (READY → SET_INTRO)
    POST /sessions/{id}/auction/open-lot   (SET_INTRO → LOT_OPEN)
    GET  /sessions/{id}/auction/state      (snapshot)

Each test creates its own session and performs its own retention confirmation
so sessions are isolated.  The shared SQLite database is safe because each
session has a unique UUID.

Also verifies:
    - live_state is correctly initialised after auction/initialize
    - live_state is lightweight (no player/bid data)
    - transition errors return 409
    - existing retention and initialization tests still work
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.database import init_db
from app.domain.enums import (
    LIVE_STATE_VERSION,
    LotStatus,
    PublicRunState,
)
from app.main import app

client = TestClient(app)


def setup_module() -> None:
    init_db(seed=True, force_seed=False)


# ---------------------------------------------------------------------------
# Fixtures (session factories)
# ---------------------------------------------------------------------------

def _create_session(team_id: int = 3) -> str:
    """Create a new session and return its ID."""
    r = client.post("/api/v1/sessions", json={"user_team_id": team_id})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _confirm_retentions(session_id: str, team_id: int = 3) -> dict:
    """Confirm 3 retentions for the given team in the session."""
    view = client.get(f"/api/v1/sessions/{session_id}/retention").json()
    players = view["eligible_players"][:3]
    r = client.post(
        f"/api/v1/sessions/{session_id}/retention",
        json={
            "retentions": [
                {"player_id": players[0]["player_id"], "slot": 1},
                {"player_id": players[1]["player_id"], "slot": 2},
                {"player_id": players[2]["player_id"], "slot": 3},
            ]
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def _setup_auction_session() -> str:
    """Create a fully initialized auction session (phase=AUCTION, live_state=READY)."""
    session_id = _create_session()
    result = _confirm_retentions(session_id)
    assert result["all_retentions_complete"] is True
    assert result["phase"] == "AUCTION"
    return session_id


# ---------------------------------------------------------------------------
# Spec #15 — live_state is correctly initialized after auction/initialize
# ---------------------------------------------------------------------------

def test_live_state_initialized_after_auction_ready() -> None:
    """After retentions are confirmed, live_state must be READY and versioned."""
    session_id = _setup_auction_session()
    r = client.get(f"/api/v1/sessions/{session_id}/auction/state")
    assert r.status_code == 200, r.text
    body = r.json()
    ls = body["live_state"]

    assert ls["version"] == LIVE_STATE_VERSION
    assert ls["public_run_state"] == PublicRunState.READY.value
    assert ls["is_accelerated"] is False
    assert ls["pause"]["active"] is False
    assert ls["countdown"]["phase"] is None
    assert ls["rtm_window"]["active"] is False
    assert ls["internal_phase"] is None
    assert "timing_ms" in ls
    assert all(v > 0 for v in ls["timing_ms"].values())


def test_live_state_is_lightweight() -> None:
    """Spec #15: live_state must not contain player, bid, or squad data."""
    session_id = _setup_auction_session()
    r = client.get(f"/api/v1/sessions/{session_id}/auction/state")
    ls = r.json()["live_state"]

    forbidden = {
        "player_id", "player_name", "current_bid_cr", "leading_team_id",
        "bid_count", "purse_remaining_cr", "squad_count", "overseas_count",
    }
    leaking = set(ls.keys()) & forbidden
    assert leaking == set(), f"live_state must not contain: {leaking!r}"


# ---------------------------------------------------------------------------
# GET /auction/state — snapshot
# ---------------------------------------------------------------------------

def test_get_state_returns_full_snapshot() -> None:
    """Snapshot must include live_state, current_lot, team_purses, and phase."""
    session_id = _setup_auction_session()
    r = client.get(f"/api/v1/sessions/{session_id}/auction/state")
    assert r.status_code == 200
    body = r.json()

    assert body["session_id"] == session_id
    assert body["phase"] == "AUCTION"
    assert body["live_state"]["public_run_state"] == "READY"
    assert body["current_lot"] is not None
    assert len(body["team_purses"]) == 10


def test_get_state_current_lot_is_pending() -> None:
    """Before open_lot(), the current lot should still be PENDING."""
    session_id = _setup_auction_session()
    body = client.get(f"/api/v1/sessions/{session_id}/auction/state").json()
    assert body["current_lot"]["status"] == LotStatus.PENDING.value


def test_get_state_current_lot_has_correct_fields() -> None:
    """Snapshot current_lot must have all expected fields."""
    session_id = _setup_auction_session()
    lot = client.get(f"/api/v1/sessions/{session_id}/auction/state").json()["current_lot"]

    assert "player_id" in lot
    assert "player_name" in lot
    assert "auction_set" in lot
    assert "set_name" in lot
    assert "base_price_cr" in lot
    assert "is_overseas" in lot
    assert "status" in lot
    # bid fields present but not yet set
    assert lot["current_bid_cr"] is None
    assert lot["leading_team_id"] is None
    assert lot["bid_count"] == 0


def test_get_state_returns_404_for_unknown_session() -> None:
    r = client.get("/api/v1/sessions/nonexistent-session-id/auction/state")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# POST /auction/start — READY → SET_INTRO
# ---------------------------------------------------------------------------

def test_start_auction_transitions_to_set_intro() -> None:
    """Spec #1 via API: POST /start should move public_run_state to SET_INTRO."""
    session_id = _setup_auction_session()
    r = client.post(f"/api/v1/sessions/{session_id}/auction/start")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["live_state"]["public_run_state"] == PublicRunState.SET_INTRO.value


def test_start_auction_persists_state_change() -> None:
    """After start_auction, GET /state must also return SET_INTRO."""
    session_id = _setup_auction_session()
    client.post(f"/api/v1/sessions/{session_id}/auction/start")
    r = client.get(f"/api/v1/sessions/{session_id}/auction/state")
    assert r.json()["live_state"]["public_run_state"] == PublicRunState.SET_INTRO.value


def test_start_auction_records_history_event() -> None:
    """start_auction must record a SET_STARTED history event."""
    from app.database import SessionLocal
    from app.models.auction_history import AuctionHistory
    from sqlalchemy import select

    session_id = _setup_auction_session()
    client.post(f"/api/v1/sessions/{session_id}/auction/start")

    with SessionLocal() as db:
        events = db.scalars(
            select(AuctionHistory)
            .where(AuctionHistory.auction_state_id == session_id)
            .where(AuctionHistory.event_type == "SET_STARTED")
        ).all()
    assert len(events) == 1
    assert events[0].payload["to_state"] == PublicRunState.SET_INTRO.value


def test_start_auction_rejected_if_not_ready() -> None:
    """Calling start_auction twice must be rejected with 409."""
    session_id = _setup_auction_session()
    client.post(f"/api/v1/sessions/{session_id}/auction/start")
    r = client.post(f"/api/v1/sessions/{session_id}/auction/start")
    assert r.status_code == 409


def test_start_auction_rejected_if_not_auction_phase() -> None:
    """start_auction must fail if the session hasn't been initialized (RETENTION phase)."""
    session_id = _create_session()  # phase = RETENTION
    r = client.post(f"/api/v1/sessions/{session_id}/auction/start")
    assert r.status_code == 409


# ---------------------------------------------------------------------------
# POST /auction/open-lot — SET_INTRO → LOT_OPEN
# ---------------------------------------------------------------------------

def test_open_lot_transitions_to_lot_open() -> None:
    """Spec #2 via API: open_lot should move public_run_state to LOT_OPEN."""
    session_id = _setup_auction_session()
    client.post(f"/api/v1/sessions/{session_id}/auction/start")
    r = client.post(f"/api/v1/sessions/{session_id}/auction/open-lot")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["live_state"]["public_run_state"] == PublicRunState.LOT_OPEN.value


def test_open_lot_marks_lot_as_live() -> None:
    """After open_lot(), the current lot status must be LIVE."""
    session_id = _setup_auction_session()
    client.post(f"/api/v1/sessions/{session_id}/auction/start")
    r = client.post(f"/api/v1/sessions/{session_id}/auction/open-lot")
    lot = r.json()["current_lot"]
    assert lot["status"] == LotStatus.LIVE.value


def test_open_lot_seeds_bid_fields() -> None:
    """open_lot seeds current_bid_cr = base_price_cr and zeroes out bid tracking."""
    session_id = _setup_auction_session()
    client.post(f"/api/v1/sessions/{session_id}/auction/start")
    r = client.post(f"/api/v1/sessions/{session_id}/auction/open-lot")
    lot = r.json()["current_lot"]

    # current_bid_cr must equal base_price_cr (bid floor)
    assert lot["current_bid_cr"] == lot["base_price_cr"]
    # No team has bid yet
    assert lot["leading_team_id"] is None
    assert lot["bid_count"] == 0


def test_open_lot_bid_fields_stored_in_pool_not_live_state() -> None:
    """Bid tracking fields must be on the lot, NOT inside live_state."""
    session_id = _setup_auction_session()
    client.post(f"/api/v1/sessions/{session_id}/auction/start")
    r = client.post(f"/api/v1/sessions/{session_id}/auction/open-lot")
    body = r.json()

    ls = body["live_state"]
    assert "current_bid_cr" not in ls
    assert "leading_team_id" not in ls
    assert "bid_count" not in ls


def test_open_lot_rejected_without_start() -> None:
    """Cannot open a lot when in READY state (must start first)."""
    session_id = _setup_auction_session()
    r = client.post(f"/api/v1/sessions/{session_id}/auction/open-lot")
    assert r.status_code == 409


def test_open_lot_records_history_event() -> None:
    """open_lot must record a LOT_OPENED history event."""
    from app.database import SessionLocal
    from app.models.auction_history import AuctionHistory
    from sqlalchemy import select

    session_id = _setup_auction_session()
    client.post(f"/api/v1/sessions/{session_id}/auction/start")
    client.post(f"/api/v1/sessions/{session_id}/auction/open-lot")

    with SessionLocal() as db:
        events = db.scalars(
            select(AuctionHistory)
            .where(AuctionHistory.auction_state_id == session_id)
            .where(AuctionHistory.event_type == "LOT_OPENED")
        ).all()
    assert len(events) == 1
    assert events[0].payload["to_state"] == PublicRunState.LOT_OPEN.value
    assert "player_id" in events[0].payload


def test_open_lot_persists_lot_open_state() -> None:
    """GET /state after open_lot must return LOT_OPEN."""
    session_id = _setup_auction_session()
    client.post(f"/api/v1/sessions/{session_id}/auction/start")
    client.post(f"/api/v1/sessions/{session_id}/auction/open-lot")
    r = client.get(f"/api/v1/sessions/{session_id}/auction/state")
    assert r.json()["live_state"]["public_run_state"] == PublicRunState.LOT_OPEN.value


# ---------------------------------------------------------------------------
# Spec #16 & #17 — Existing tests still pass
# (confirmed by running the full test suite, but we also verify
# the key contracts here to be explicit)
# ---------------------------------------------------------------------------

def test_existing_retention_flow_still_works() -> None:
    """Regression: retention confirm must still return correct purse figures."""
    session_id = _create_session()
    result = _confirm_retentions(session_id)
    assert result["summary"]["total_retention_cost_cr"] == "41.00"
    assert result["summary"]["remaining_purse_cr"] == "79.00"


def test_existing_auction_initialization_still_works() -> None:
    """Regression: auction/initialize must still return 291-lot pool."""
    session_id = _setup_auction_session()
    r = client.get(f"/api/v1/sessions/{session_id}/auction/initialize")
    assert r.status_code == 200
    body = r.json()
    assert body["phase"] == "AUCTION"
    assert body["pool_stats"]["pool_count"] == 291


def test_initialization_now_also_sets_live_state() -> None:
    """auction/initialize must also initialise live_state to READY."""
    session_id = _setup_auction_session()
    # GET /state must return versioned READY state
    r = client.get(f"/api/v1/sessions/{session_id}/auction/state")
    assert r.status_code == 200
    ls = r.json()["live_state"]
    assert ls["version"] == LIVE_STATE_VERSION
    assert ls["public_run_state"] == "READY"


def test_team_purses_returned_in_snapshot() -> None:
    """Snapshot must include all 10 team purses with correct retained values."""
    session_id = _setup_auction_session()
    r = client.get(f"/api/v1/sessions/{session_id}/auction/state")
    purses = r.json()["team_purses"]
    assert len(purses) == 10
    for purse in purses:
        # Every team has retained 3 players for 41 Cr → 79 Cr remaining
        assert purse["purse_remaining_cr"] == "79.00"
        assert purse["squad_count"] == 3
