from flask import jsonify, request
from sqlalchemy.orm import joinedload
from werkzeug.http import HTTP_STATUS_CODES

from app import db
from app.api import api
from app.models import Account, User
from app.finance.accounts import AccountManager


def error_response(status_code, message=None):
    payload = {'error': HTTP_STATUS_CODES.get(status_code, 'Unknown error')}
    if message:
        payload['message'] = message
    response = jsonify(payload)
    response.status_code = status_code
    return response


def response(payload, status_code=200):
    response = jsonify(payload)
    response.status_code = status_code
    return response


@api.route('/user/<int:user_id>')
def get_user(user_id):
    user = User.query.get_or_404(user_id)
    payload = user.get_api_repr()
    return response(payload)


@api.route('/user', methods=['POST'])
def create_user():
    data = request.get_json() or {}
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')

    if not (username and email and password):
        return error_response(400, 'must include username, email, and password')
    if User.query.filter_by(username=username).first():
        return error_response(400, 'username has been taken')
    if User.query.filter_by(email=email).first():
        return error_response(400, 'email has been taken')

    user = User(username=username, email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    payload = user.get_api_repr()
    return response(payload, 201)


@api.route('/user/<int:user_id>/accounts')
def get_user_accounts(user_id):
    user = (
        User.query.filter(User.id == user_id)
        .options(joinedload(User.accounts))
        .first_or_404()
    )
    payload = {'accounts': []}
    for account in user.accounts:
        account_data = {
            'id': account.id,
            'name': account.name,
            'type': account.category.name,
            'current_balance': round(account.get_ending_balance(), 2),
        }
        payload['accounts'].append(account_data)
    return response(payload)


@api.route('/user/<int:user_id>/stocks')
def get_user_current_stocks(user_id):
    user = (
        User.query.filter(User.id == user_id)
        .options(joinedload(User.accounts))
        .first_or_404()
    )
    account_manager = AccountManager(user.accounts)
    stocks_data = account_manager.get_current_stock_holdings()
    return response(stocks_data)
