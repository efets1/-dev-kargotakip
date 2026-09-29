import os

from flask import Flask

from app.models import init_db


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE=os.environ.get("CARGO_DATABASE", os.path.join(app.instance_path, "cargo.sqlite3")),
        KAFKA_BOOTSTRAP_SERVERS=os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
    )

    if test_config is not None:
        app.config.update(test_config)

    os.makedirs(app.instance_path, exist_ok=True)
    init_db(app)

    from app.routes import cargo_bp

    app.register_blueprint(cargo_bp)
    return app