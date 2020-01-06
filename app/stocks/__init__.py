from flask import Blueprint

stocks = Blueprint('stocks', __name__, template_folder='templates')

from app.stocks import views
