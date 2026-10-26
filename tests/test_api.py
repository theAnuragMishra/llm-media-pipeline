"""Unit & integration tests for FastAPI routes and task lifecycle."""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_endpoint():
    """Verify health endpoint reports service health and broker status."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "broker_mode" in data


def test_generate_course_video_endpoint():
    """Verify POST /api/v1/generate-course-video validates payload and returns 202 Accepted."""
    payload = {
        "topic": "Photosynthesis",
        "target_scenes": 2,
        "voice": "en-US-ChristopherNeural",
        "resolution": "1080p",
    }
    response = client.post("/api/v1/generate-course-video", json=payload)
    assert response.status_code == 202
    data = response.json()
    assert "task_id" in data
    assert data["topic"] == "Photosynthesis"
    assert data["status"] == "ACCEPTED"
    assert "/api/v1/tasks/" in data["poll_url"]
    assert "/api/v1/tasks/" in data["sse_url"]
    assert "/ws/tasks/" in data["ws_url"]


def test_get_task_status():
    """Verify task query returns initial or updated state."""
    # Enqueue a task
    post_res = client.post("/api/v1/generate-course-video", json={"topic": "Distributed Consensus"})
    task_id = post_res.json()["task_id"]

    # Poll status
    get_res = client.get(f"/api/v1/tasks/{task_id}")
    assert get_res.status_code == 200
    status_data = get_res.json()
    assert status_data["task_id"] == task_id
    assert status_data["topic"] == "Distributed Consensus"
    assert "stage" in status_data
    assert "progress_percent" in status_data


def test_get_nonexistent_task():
    """Verify 404 is returned for an invalid task ID."""
    response = client.get("/api/v1/tasks/task_does_not_exist_999")
    assert response.status_code == 404
