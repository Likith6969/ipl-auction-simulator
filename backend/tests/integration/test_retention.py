from fastapi.testclient import TestClient

from app.database import init_db
from app.main import app

client = TestClient(app)


def setup_module() -> None:
    init_db(seed=True, force_seed=False)


def _create_mi_session() -> str:
    response = client.post("/api/v1/sessions", json={"user_team_id": 3})
    assert response.status_code == 201
    return response.json()["id"]


def test_get_retention_players_for_mi() -> None:
    session_id = _create_mi_session()
    response = client.get(f"/api/v1/sessions/{session_id}/retention")
    assert response.status_code == 200
    body = response.json()
    assert body["short_name"] == "MI"
    assert len(body["eligible_players"]) == 15
    assert body["summary"]["initial_purse_cr"] == "120.00"
    assert body["is_confirmed"] is False
    assert len(body["retention_costs"]) == 3


def test_confirm_retentions() -> None:
    session_id = _create_mi_session()
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
    body = response.json()
    assert body["summary"]["total_retention_cost_cr"] == "41.00"
    assert body["summary"]["remaining_purse_cr"] == "79.00"
    assert len(body["retentions"]) == 3


def test_duplicate_confirm_rejected() -> None:
    session_id = _create_mi_session()
    view = client.get(f"/api/v1/sessions/{session_id}/retention").json()
    players = view["eligible_players"][:3]
    payload = {
        "retentions": [
            {"player_id": players[0]["player_id"], "slot": 1},
            {"player_id": players[1]["player_id"], "slot": 2},
            {"player_id": players[2]["player_id"], "slot": 3},
        ]
    }
    client.post(f"/api/v1/sessions/{session_id}/retention", json=payload)
    retry = client.post(f"/api/v1/sessions/{session_id}/retention", json=payload)
    assert retry.status_code == 409
