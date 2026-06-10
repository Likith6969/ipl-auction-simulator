from fastapi.testclient import TestClient

from app.database import SessionLocal, init_db
from app.main import app
from app.models.auction_state import AuctionState

client = TestClient(app)


def setup_module() -> None:
    init_db(seed=True, force_seed=False)


def _create_session(team_id: int = 3) -> str:
    response = client.post("/api/v1/sessions", json={"user_team_id": team_id})
    assert response.status_code == 201
    return response.json()["id"]


def _confirm_mi_retentions(session_id: str) -> dict:
    view = client.get(f"/api/v1/sessions/{session_id}/retention").json()
    players = view["eligible_players"][:3]
    response = client.post(
        f"/api/v1/sessions/{session_id}/retention",
        json={
            "retentions": [
                {"player_id": players[0]["player_id"], "slot": 1},
                {"player_id": players[1]["player_id"], "slot": 2},
                {"player_id": players[2]["player_id"], "slot": 3},
            ]
        },
    )
    assert response.status_code == 201
    return response.json()


def test_initialize_via_retention_confirm() -> None:
    session_id = _create_session()
    _confirm_mi_retentions(session_id)

    init_response = client.get(f"/api/v1/sessions/{session_id}/auction/initialize")
    assert init_response.status_code == 200
    body = init_response.json()
    assert body["phase"] == "AUCTION"
    assert body["all_retentions_complete"] is True
    assert body["pool_stats"]["retained_count"] == 30
    assert body["pool_stats"]["pool_count"] == 321 - 30
    assert body["current_player_id"] is not None
    assert body["already_initialized"] is True

    with SessionLocal() as db:
        state = db.get(AuctionState, session_id)
        assert state is not None
        retained_in_pool = {
            lot["player_id"]
            for lot in state.auction_pool["lots"]
        }
        assert not retained_in_pool.intersection(set(state.auction_pool["retained_player_ids"]))
        assert all(
            purse["purse_remaining_cr"] == "79.00"
            for purse in body["team_purses"]
        )


def test_initialize_requires_user_retentions() -> None:
    session_id = _create_session()
    response = client.post(f"/api/v1/sessions/{session_id}/auction/initialize")
    assert response.status_code == 422
