from fastapi.testclient import TestClient

from app.database import init_db
from app.main import app

client = TestClient(app)


def setup_module() -> None:
    init_db(seed=True, force_seed=False)


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


def test_ai_retentions_run_for_remaining_teams() -> None:
    session_id = client.post("/api/v1/sessions", json={"user_team_id": 3}).json()["id"]
    result = _confirm_mi_retentions(session_id)

    assert result["ai_teams_retained"] == 9
    assert result["all_retentions_complete"] is True
    assert result["phase"] == "AUCTION"

    all_retentions = client.get(f"/api/v1/sessions/{session_id}/retention/all").json()
    assert all_retentions["all_retentions_complete"] is True
    assert len(all_retentions["teams"]) == 10
    assert all(team["is_confirmed"] for team in all_retentions["teams"])


def test_csk_ai_retains_captain() -> None:
    session_id = client.post("/api/v1/sessions", json={"user_team_id": 3}).json()["id"]
    _confirm_mi_retentions(session_id)

    all_retentions = client.get(f"/api/v1/sessions/{session_id}/retention/all").json()
    csk = next(team for team in all_retentions["teams"] if team["short_name"] == "CSK")
    slot_one = next(item for item in csk["retentions"] if item["retention_slot"] == 1)
    assert slot_one["player"]["name"] == "Ruturaj Gaikwad"
    assert slot_one["player"]["is_captain"] is True
