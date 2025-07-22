from flask import Flask
from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()


def create_app():
    from .routes import register_routes
    app = Flask(__name__)

    from config import Config
    app.config.from_object(Config)

    db.init_app(app)

    with app.app_context():
        from .models import User, Position, EloHistory
        db.create_all()

    register_routes(app)

    return app
