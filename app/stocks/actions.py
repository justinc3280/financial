from flask import redirect, render_template, request, url_for
from flask_login import login_required

from app import db
from app.models import Transaction
from app.stocks import stocks
from app.stocks.forms import StockTransactionForm


@stocks.route('/stock_transaction/<int:transaction_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_stock_transaction(transaction_id):
    stock_transaction = Transaction.query.get_or_404(transaction_id)
    properties = stock_transaction.get_properties()

    cost_basis = properties.get('cost_basis')
    if not cost_basis and stock_transaction.category.name in [
        'Buy',
        'Dividend Reinvest',
    ]:
        cost_basis = abs(stock_transaction.amount)

    data = {
        'symbol': properties.get('symbol'),
        'quantity': properties.get('quantity'),
        'transaction_fee': properties.get('transaction_fee'),
        'cost_basis': cost_basis,
        'market_value': properties.get('market_value'),
        'split_adjustment': properties.get('split_adjustment'),
    }

    form = StockTransactionForm(data=data)

    if request.form:
        properties = {
            'symbol': form.symbol.data,
            'quantity': form.quantity.data,
            'transaction_fee': form.transaction_fee.data,
            'cost_basis': form.cost_basis.data,
            'market_value': form.market_value.data,
        }

        if form.split_adjustment.data:
            properties['split_adjustment'] = form.split_adjustment.data
        else:
            stock_transaction.remove_property('split_adjustment')

        stock_transaction.update_properties(properties)

        db.session.commit()
        return redirect(url_for('stocks.stock_transactions'))
    return render_template(
        'stocks/forms/edit_stock_transaction.html',
        form=form,
        transaction=stock_transaction,
    )
