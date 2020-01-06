import logging
import os

from flask import Flask
from config import Config
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from werkzeug.debug import DebuggedApplication

logger = logging.getLogger(__name__)

db = SQLAlchemy()
migrate = Migrate()
login = LoginManager()
login.login_view = 'auth.login'

from app.api import api as api_bp
from app.auth import auth as auth_bp
from app.caching import cache
from app.errors import errors as errors_bp
from app.finance import finance as finance_bp
from app.stocks import stocks as stocks_bp
from app.jinja import register_jinja_filters


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)

    if app.debug:
        app.wsgi_app = DebuggedApplication(app.wsgi_app, evalex=True)

    db.init_app(app)
    migrate.init_app(app, db)
    login.init_app(app)

    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(errors_bp)
    app.register_blueprint(finance_bp)
    app.register_blueprint(stocks_bp)

    register_jinja_filters(app.jinja_env)

    logger.setLevel(logging.DEBUG)
    log_format = '[%(asctime)s] [%(name)s:%(lineno)d] [%(levelname)s] %(message)s'
    logging_formatter = logging.Formatter(log_format)

    log_console_handler = logging.StreamHandler()
    log_console_handler.setLevel(logging.DEBUG)
    log_console_handler.setFormatter(logging_formatter)
    logger.addHandler(log_console_handler)

    if not app.debug:
        if not os.path.exists('logs'):
            os.mkdir('logs')

        log_file_handler = logging.handlers.RotatingFileHandler(
            'logs/financial.log', maxBytes=10240, backupCount=10
        )
        log_file_handler.setFormatter(logging_formatter)
        log_file_handler.setLevel(logging.INFO)
        logger.addHandler(log_file_handler)

    cache.connect(app.config['REDIS_HOST'], app.config['REDIS_PORT'])
    logger.info('Financial App initialized, Debug=%s', app.debug)

    return app


from app import jinja, models
