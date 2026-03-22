import os
from flask import Flask
from config import Config
from app.extensions import db, login_manager


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Ensure upload folder exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Init extensions
    db.init_app(app)
    login_manager.init_app(app)

    # Register blueprints
    from app.auth import auth_bp
    from app.main import main_bp
    from app.files import files_bp
    from app.chat import chat_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(files_bp)
    app.register_blueprint(chat_bp)

    # Create database tables
    with app.app_context():
        from app import models  # noqa: F401
        db.create_all()

    return app
