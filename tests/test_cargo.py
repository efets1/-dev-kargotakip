import pytest

from app import create_app
from app.routes import publish_cargo_event


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr("app.routes.publish_cargo_event", lambda *_args, **_kwargs: True)
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "cargo-test.sqlite3")})
    with app.test_client() as test_client:
        yield test_client


def create_cargo(client, tracking_number="TRK-001"):
    return client.post(
        "/cargo",
        json={"tracking_number": tracking_number, "sender": "Aylin", "receiver": "Deniz"},
    )


def test_create_cargo_returns_pending_shipment(client):
    response = create_cargo(client)
    assert response.status_code == 201
    assert response.json["tracking_number"] == "TRK-001"
    assert response.json["status"] == "pending"
    assert response.json["created_at"]


def test_create_cargo_requires_all_fields(client):
    response = client.post("/cargo", json={"tracking_number": "TRK-001"})
    assert response.status_code == 400


def test_duplicate_tracking_number_is_rejected(client):
    create_cargo(client)
    response = create_cargo(client)
    assert response.status_code == 409


def test_get_cargo_by_id(client):
    created = create_cargo(client)
    response = client.get(f"/cargo/{created.json['id']}")
    assert response.status_code == 200
    assert response.json["sender"] == "Aylin"


def test_get_missing_cargo_returns_404(client):
    assert client.get("/cargo/999").status_code == 404


def test_list_cargo_returns_created_shipments(client):
    create_cargo(client)
    create_cargo(client, "TRK-002")
    response = client.get("/cargo")
    assert response.status_code == 200
    assert len(response.json) == 2


def test_status_can_be_updated(client):
    created = create_cargo(client)
    response = client.put(f"/cargo/{created.json['id']}/status", json={"status": "in_transit"})
    assert response.status_code == 200
    assert response.json["status"] == "in_transit"


def test_invalid_status_is_rejected(client):
    created = create_cargo(client)
    response = client.put(f"/cargo/{created.json['id']}/status", json={"status": "lost"})
    assert response.status_code == 400


def test_delivered_cargo_cannot_be_dispatched_again(client):
    created = create_cargo(client)
    cargo_id = created.json["id"]
    delivered = client.put(f"/cargo/{cargo_id}/status", json={"status": "delivered"})
    assert delivered.status_code == 200
    response = client.put(f"/cargo/{cargo_id}/status", json={"status": "out_for_delivery"})
    assert response.status_code == 400
    assert client.get(f"/cargo/{cargo_id}").json["status"] == "delivered"


def test_delete_cargo(client):
    created = create_cargo(client)
    cargo_id = created.json["id"]
    assert client.delete(f"/cargo/{cargo_id}").status_code == 204
    assert client.get(f"/cargo/{cargo_id}").status_code == 404


def test_metrics_endpoint_exposes_required_metrics(client):
    create_cargo(client)
    response = client.get("/metrics")
    assert response.status_code == 200
    for metric in (
        "cargo_created_total",
        "cargo_delivered_total",
        "cargo_cancelled_total",
        "cargo_status_changed_total",
        "api_request_duration",
    ):
        assert metric in response.text