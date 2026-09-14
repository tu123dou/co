"""无需数据库的 HTTP 边界回归。"""

from app.main import create_app
from fastapi.testclient import TestClient


def test_routes_require_authentication_without_database_access():
    with TestClient(create_app()) as client:
        for path in [
            "/api/catalog",
            "/api/conversations",
            "/api/favorites",
            "/api/feedbacks",
            "/api/workbench/settings",
        ]:
            assert client.get(path).status_code == 401
        response = client.post("/api/conversations")
        assert response.status_code == 401
        assert response.headers["cache-control"] == "no-store"


def test_invalid_origin_is_rejected_before_authentication():
    with TestClient(create_app()) as client:
        response = client.post(
            "/api/conversations", headers={"Origin": "https://untrusted.invalid"}
        )
        assert response.status_code == 403
