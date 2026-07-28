from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.observability import install_observability


def test_prometheus_endpoint_exports_matchmaking_and_http_metrics():
    app = FastAPI()
    values = {
        "queue_depth": 3.0,
        "total_enqueues": 10.0,
        "total_matches": 4.0,
        "sla_forced_matches": 1.0,
        "sla_forced_percentage": 25.0,
        "current_threshold": 150.0,
    }
    install_observability(app, lambda: values)

    @app.get("/hello")
    async def hello():
        return {"ok": True}

    client = TestClient(app)
    assert client.get("/hello").status_code == 200

    response = client.get("/prometheus")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    body = response.text

    assert "matchmaking_queue_depth 3.0" in body
    assert "matchmaking_total_matches 4.0" in body
    assert "matchmaking_current_threshold 150.0" in body
    assert 'matchmaking_http_requests_total{method="GET",route="/hello",status="200"} 1.0' in body
    assert "matchmaking_http_request_duration_seconds_bucket" in body


def test_collector_reads_fresh_shared_state_on_each_scrape():
    app = FastAPI()
    values = {"queue_depth": 1.0}
    install_observability(app, lambda: values)
    client = TestClient(app)

    assert "matchmaking_queue_depth 1.0" in client.get("/prometheus").text
    values["queue_depth"] = 7.0
    assert "matchmaking_queue_depth 7.0" in client.get("/prometheus").text
