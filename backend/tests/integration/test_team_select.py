from fastapi.testclient import TestClient

from app.database import init_db
from app.main import app

client = TestClient(app)


def setup_module() -> None:
    init_db(seed=True, force_seed=False)


def test_list_teams() -> None:
    response = client.get("/api/v1/teams")
    assert response.status_code == 200
    teams = response.json()
    assert len(teams) == 10
    assert teams[0]["short_name"] == "RCB"


def test_create_session_and_get() -> None:
    response = client.post("/api/v1/sessions", json={"user_team_id": 3})
    assert response.status_code == 201
    body = response.json()
    assert body["phase"] == "RETENTION"
    assert body["user_team"]["short_name"] == "MI"

    session_id = body["id"]
    get_response = client.get(f"/api/v1/sessions/{session_id}")
    assert get_response.status_code == 200
    assert get_response.json()["id"] == session_id


def test_create_session_invalid_team() -> None:
    response = client.post("/api/v1/sessions", json={"user_team_id": 99})
    assert response.status_code == 404
