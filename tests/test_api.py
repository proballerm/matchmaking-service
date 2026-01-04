from fastapi.testclient import TestClient

from api.app import app


def test_api_enqueue_tick_matches_flow():
    client = TestClient(app)

    r1 = client.post("/enqueue", json={"player_id": "p1", "rating": 1000})
    assert r1.status_code == 200

    r2 = client.post("/enqueue", json={"player_id": "p2", "rating": 1010})
    assert r2.status_code == 200

    r3 = client.post("/tick", json={})
    assert r3.status_code == 200

    r4 = client.get("/matches")
    assert r4.status_code == 200
    body = r4.json()
    assert "matches" in body
    assert len(body["matches"]) == 1
