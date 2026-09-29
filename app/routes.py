import sqlite3
import time

from flask import Blueprint, Response, g, jsonify, request
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

from app.kafka_producer import publish_cargo_event
from app.models import STATUSES, cargo_to_dict, get_db, utc_now


cargo_bp = Blueprint("cargo", __name__)
cargo_created_total = Counter("cargo_created_total", "Number of cargo shipments created")
cargo_delivered_total = Counter("cargo_delivered_total", "Number of cargo shipments delivered")
cargo_cancelled_total = Counter("cargo_cancelled_total", "Number of cargo shipments cancelled")
cargo_status_changed_total = Counter("cargo_status_changed_total", "Number of cargo status changes")
api_request_duration = Histogram("api_request_duration", "API request duration in seconds")


@cargo_bp.before_app_request
def start_request_timer():
    g.request_started_at = time.perf_counter()


@cargo_bp.after_app_request
def record_request_duration(response):
    started_at = getattr(g, "request_started_at", None)
    if started_at is not None:
        api_request_duration.observe(time.perf_counter() - started_at)
    return response


def _error(message, status_code):
    return jsonify(error=message), status_code


def _required_text(data, field):
    value = data.get(field)
    return value.strip() if isinstance(value, str) else ""


@cargo_bp.post("/cargo")
def create_cargo():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return _error("Request body must be a JSON object", 400)

    values = {field: _required_text(data, field) for field in ("tracking_number", "sender", "receiver")}
    if not all(values.values()):
        return _error("tracking_number, sender, and receiver are required", 400)

    db = get_db()
    try:
        cursor = db.execute(
            "INSERT INTO cargo (tracking_number, sender, receiver, status, created_at) VALUES (?, ?, ?, ?, ?)",
            (values["tracking_number"], values["sender"], values["receiver"], "pending", utc_now()),
        )
        db.commit()
    except sqlite3.IntegrityError:
        db.rollback()
        return _error("tracking_number already exists", 409)

    cargo = cargo_to_dict(db.execute("SELECT * FROM cargo WHERE id = ?", (cursor.lastrowid,)).fetchone())
    cargo_created_total.inc()
    publish_cargo_event("cargo.created", cargo)
    return jsonify(cargo), 201


@cargo_bp.get("/cargo/<int:cargo_id>")
def get_cargo(cargo_id):
    cargo = get_db().execute("SELECT * FROM cargo WHERE id = ?", (cargo_id,)).fetchone()
    if cargo is None:
        return _error("Cargo not found", 404)
    return jsonify(cargo_to_dict(cargo))


@cargo_bp.get("/cargo")
def list_cargo():
    cargos = get_db().execute("SELECT * FROM cargo ORDER BY id").fetchall()
    return jsonify([cargo_to_dict(cargo) for cargo in cargos])


@cargo_bp.put("/cargo/<int:cargo_id>/status")
def update_cargo_status(cargo_id):
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get("status"), str):
        return _error("A status value is required", 400)

    new_status = data["status"].strip().lower()
    if new_status not in STATUSES:
        return _error(f"Invalid status. Allowed values: {', '.join(sorted(STATUSES))}", 400)

    db = get_db()
    current = db.execute("SELECT * FROM cargo WHERE id = ?", (cargo_id,)).fetchone()
    if current is None:
        return _error("Cargo not found", 404)
    if current["status"] in {"delivered", "cancelled"} and new_status != current["status"]:
        return _error(f"Cargo with status '{current['status']}' cannot be changed", 400)
    if current["status"] == new_status:
        return jsonify(cargo_to_dict(current))

    db.execute("UPDATE cargo SET status = ? WHERE id = ?", (new_status, cargo_id))
    db.commit()
    cargo = cargo_to_dict(db.execute("SELECT * FROM cargo WHERE id = ?", (cargo_id,)).fetchone())
    cargo_status_changed_total.inc()
    if new_status == "delivered":
        cargo_delivered_total.inc()
        publish_cargo_event("cargo.delivered", cargo)
    elif new_status == "cancelled":
        cargo_cancelled_total.inc()
        publish_cargo_event("cargo.status_changed", cargo)
    else:
        publish_cargo_event("cargo.status_changed", cargo)
    return jsonify(cargo)


@cargo_bp.delete("/cargo/<int:cargo_id>")
def delete_cargo(cargo_id):
    db = get_db()
    cursor = db.execute("DELETE FROM cargo WHERE id = ?", (cargo_id,))
    if cursor.rowcount == 0:
        return _error("Cargo not found", 404)
    db.commit()
    return "", 204


@cargo_bp.get("/metrics")
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)