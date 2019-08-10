from flask import Flask
from config import Config
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager

db = SQLAlchemy()
migrate = Migrate()
login = LoginManager()
login.login_view = 'auth.login'

from app.api import api as api_bp
from app.auth import auth as auth_bp
from app.errors import errors as errors_bp
from app.finance import finance as finance_bp
from app.jinja import register_jinja_filters


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)

    db.init_app(app)
    migrate.init_app(app, db)
    login.init_app(app)

    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(errors_bp)
    app.register_blueprint(finance_bp)

    register_jinja_filters(app.jinja_env)

    return app


from app import jinja, models
