from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_media_catalog_lists_assets() -> None:
    res = client.get("/api/v1/media/catalog")
    assert res.status_code == 200
    body = res.json()
    assert body["videos"]
    assert body["sounds"]
    assert body["lights"]
    assert body["videos"][0]["path"].startswith("media/")
    assert body["touchdesigner"]["addresses"]["play_clip"] == "/visual/play_clip"
