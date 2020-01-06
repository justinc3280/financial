from flask import render_template, request
from flask_login import current_user, login_required

from app.models import Account, Category, Transaction
from app.stocks import stocks
from app.stocks.stock import StocksManager
from app.utils import current_date


@stocks.route('/stock_transactions')
@login_required
def stock_transactions():
    stock_transactions = (
        Transaction.query.join(Transaction.category)
        .join(Transaction.account)
        .filter(
            Category.name.in_(
                [
                    'Buy',
                    'Sell',
                    'Dividend Reinvest',
                    'Transfer Stock In',
                    'Transfer Stock Out',
                ]
            ),
            Account.user == current_user,
        )
        .order_by(Transaction.date)
        .all()
    )

    return render_template(
        "stocks/stock_transactions.html", stock_transactions=stock_transactions
    )


@stocks.route('/stocks')
@login_required
def current_holdings():
    brokerage_accounts = Account.get_brokerage_accounts(user_id=current_user.id)
    stocks_manager = StocksManager(accounts=brokerage_accounts)
    current_holdings = stocks_manager.get_current_holdings()
    return render_template("stocks/stocks.html", current_holdings=current_holdings)


@stocks.route('/stocks/return/data')
@login_required
def stocks_return_data():
    year = int(request.args.get('year', date.today().year))
    brokerage_accounts = Account.get_brokerage_accounts(user_id=current_user.id)
    stocks_manager = StocksManager(accounts=brokerage_accounts)
    annual_return = stocks_manager.get_monthly_roi_data(year)
    return render_template('stocks/return_data.html', annual_return=annual_return)


@stocks.route('/stocks/return/')
@login_required
def stocks_return():
    start_year = 2011
    end_year = int(request.args.get('year', current_date.year))

    brokerage_accounts = Account.get_brokerage_accounts(user_id=current_user.id)
    stocks_manager = StocksManager(accounts=brokerage_accounts)
    multi_year_return = stocks_manager.get_compounded_roi(start_year, end_year)
    return render_template('stocks/return.html', multi_year_return=multi_year_return)
