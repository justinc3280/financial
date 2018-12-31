from app import db
from app.finance import finance, stock_values
from app.finance.stock_values import get_current_price
from flask import redirect, render_template, request, url_for
from flask_login import current_user, login_required
from app.models import Account, AccountType, Category, Paycheck, StockTransaction, Transaction
from datetime import date
import calendar
from collections import defaultdict

@finance.route('/')
@finance.route('/index')
@login_required
def index():
    return redirect(url_for('finance.income_statement'))

@finance.route('/accounts')
@login_required
def accounts():
    accounts = Account.query.filter(Account.user==current_user).all()
    return render_template('finance/accounts.html', title='Accounts', accounts=accounts)

@finance.route('/account/<int:account_id>/')
@login_required
def account_details(account_id):
    account = Account.query.filter_by(id = account_id).first_or_404()
    return render_template('finance/account_details.html', account=account)

@finance.route('/account_types')
@login_required
def account_types():
    account_types = AccountType.query.all()

    return render_template("finance/account_types.html", account_types=account_types)


def get_stock_values(end_date=date.today()):
    stocks_data = {'Total': {'cost': 0}}
    stock_transactions = Transaction.query.join(Transaction.category).join(Transaction.account).filter(
        Transaction.date <= end_date, Category.name.in_(['Buy', 'Sell']), Account.user==current_user).all()
    for stock_transaction in stock_transactions:
        properties = stock_transaction.get_properties()
        symbol = properties.get('symbol')
        if symbol:
            if symbol not in stocks_data:
                stocks_data[symbol] = {
                    'quantity': 0,
                    'cost': 0
                }

            if stock_transaction.category.name == 'Buy':
                stocks_data[symbol]['quantity'] += properties.get('quantity')
                stocks_data[symbol]['cost'] += abs(stock_transaction.amount)
                stocks_data['Total']['cost'] += abs(stock_transaction.amount)
            elif stock_transaction.category.name == 'Sell':
                stocks_data[symbol]['quantity'] -= properties.get('quantity')
                stocks_data[symbol]['cost'] -= abs(stock_transaction.amount)
                stocks_data['Total']['cost'] -= abs(stock_transaction.amount)
            stocks_data[symbol]['cost_per_share'] = stocks_data[symbol]['cost'] / stocks_data[symbol]['quantity']

    # for symbol, stock_data in stocks_data.items():
        # current_price = get_current_price(symbol)
        # if current_price:
        #     stock_data['current_price'] = current_price
        #     stock_data['market_value'] = stock_data['quantity'] * stock_data['current_price']
    return stocks_data


@finance.route('/stocks')
@login_required
def stocks():
    stocks_data = get_stock_values()

    return render_template("finance/stocks.html", stock_data=stocks_data)


@finance.route('/stock_transactions')
@login_required
def stock_transactions():
    stock_transactions = Transaction.query.join(Transaction.category).join(Transaction.account).filter(Category.name.in_(['Buy', 'Sell']), Account.user==current_user).all()

    return render_template("finance/stock_transactions.html", stock_transactions=stock_transactions)


@finance.route('/account/<int:account_id>/view_transactions')
@login_required
def view_transactions(account_id):
    account = Account.query.filter(Account.id == account_id).first_or_404()
    return render_template('finance/transactions.html', transactions=account.transactions)

@finance.route('/categories')
@login_required
def categories():
    root_categories = Category.query.filter(Category.parent == None).all()
    return render_template('finance/categories.html', categories=root_categories)

@finance.route('/paychecks/')
@login_required
def paychecks():
    paychecks = Paycheck.query.filter(Paycheck.user==current_user).all()
    return render_template('finance/paychecks.html', paychecks=paychecks)

def month_choices():
    choices = []
    for i, month in enumerate(calendar.month_name):
        if i == 0:
            month = "Select Month"
        choices.append((i, month))
    return choices

@finance.route('/balance_sheet')
@login_required
def balance_sheet():
    year = 2018

    months = list(calendar.month_name)[1:]
    ending_month_dates = []
    for month_num in range(1, 12):
        last_day = calendar.monthrange(year, month_num)[1]
        ending_month_dates.append(date(year, month_num, last_day))

    accounts_monthly_ending_balance = {}
    for account in current_user.accounts:
        ending_balances = [account.get_ending_balance(date) for date in ending_month_dates]
        accounts_monthly_ending_balance[account.name] = ending_balances

        parent_categories = account.category.get_parent_categories() if account.category else []
        for parent in parent_categories:
            if parent.name not in accounts_monthly_ending_balance:
                accounts_monthly_ending_balance[parent.name] = [0] * len(ending_month_dates)
            update_category_balances = add_lists(accounts_monthly_ending_balance.get(parent.name), ending_balances)
            accounts_monthly_ending_balance[parent.name] = update_category_balances

    total_current_assetts = accounts_monthly_ending_balance.get('Current Assetts', [0] * len(ending_month_dates))
    total_current_liabilities = accounts_monthly_ending_balance.get('Current Liabilities', [0] * len(ending_month_dates))
    accounts_monthly_ending_balance['working_capital'] = add_lists(total_current_assetts, total_current_liabilities)

    total_assetts = accounts_monthly_ending_balance.get('Assetts', [0] * len(ending_month_dates))
    total_liabilities = accounts_monthly_ending_balance.get('Liabilities', [0] * len(ending_month_dates))
    accounts_monthly_ending_balance['net_worth'] = add_lists(total_assetts, total_liabilities)

    root_categories = Category.query.filter(Category.parent == None, Category.name.in_(['Assetts', 'Liabilities'])).all()

    return render_template("finance/balance_sheet.html",
                            root_categories=root_categories,
                            category_monthly_totals=accounts_monthly_ending_balance,
                            month_choices=month_choices())

def paycheck_col_to_category_name(col_name):
    translation = {
        'gross_pay': 'Gross Pay',
        'federal_income_tax': 'Federal Income Tax',
        'social_security_tax': 'Social Security Tax',
        'medicare_tax': 'Medicare Tax',
        'state_income_tax': 'State Income Tax',
        'health_insurance': 'Health Insurance Premium',
        'dental_insurance': 'Dental Insurance Premium',
        'traditional_retirement': 'Traditional 401K Contribution',
        'roth_retirement': 'Roth 401K Contribution',
        'retirement_match': '401K Match',
        'gtl': 'G.T.L.',
        'gtl_in': 'G.T.L. In',
        #'gym_reimbursement': 'Gym Reimbursement',
        'gym_reimbursement': 'Other Income',
        'net_pay': 'Net Pay'
    }
    return translation[col_name]

def convert_paychecks_to_transactions(paychecks):
    transactions = []
    for paycheck in paychecks:
        paycheck_dict = paycheck.__dict__
        paycheck_date = paycheck_dict.get('date')
        for key, value in paycheck.get_properties().items():
            paycheck_dict[key] = value
            if key == 'gtl':
                paycheck_dict['gtl_in'] = value

        [paycheck_dict.pop(k) for k in ['_sa_instance_state', 'id', 'user_id', 'company_name', 'date', 'properties']]

        for key, value in paycheck_dict.items():
            if key not in ['gross_pay', 'net_pay', 'gym_reimbursement', 'gtl_in']:
                value = -value
            cat_name = paycheck_col_to_category_name(key)
            category = Category.query.filter(Category.name==cat_name).first()
            top_level_category = category.top_level_parent()
            if top_level_category.name in ["Income", "Expense", "Tax"]:
                transaction = Transaction(
                    amount = value,
                    date = paycheck_date,
                    category = category
                )
                transactions.append(transaction)
    return transactions

def get_category_monthly_totals(start_date, end_date):
    num_months = end_date.month - start_date.month + 1

    transactions = Transaction.query.join(Account, Account.id==Transaction.account_id).filter(Account.user_id==current_user.id, Transaction.date.between(start_date, end_date)).all()
    paychecks = Paycheck.query.filter(Paycheck.user_id==current_user.id, Paycheck.date.between(start_date, end_date)).all()

    paycheck_transactions = convert_paychecks_to_transactions(paychecks)
    transactions.extend(paycheck_transactions)

    category_monthly_totals = {}
    for transaction in transactions:
        parent_categories = transaction.category.get_parent_categories()
        for parent_category in parent_categories:
            if parent_category.name not in category_monthly_totals:
                category_monthly_totals[parent_category.name] = {index: total for index, total in enumerate([0] * num_months)}
            category_monthly_totals[parent_category.name][transaction.date.month - 1] += transaction.amount

    total_income = category_monthly_totals.get('Income').values() if category_monthly_totals.get('Income') else [0] * num_months
    total_tax = category_monthly_totals.get('Tax').values() if category_monthly_totals.get('Tax') else [0] * num_months
    total_expense = category_monthly_totals.get('Expense').values() if category_monthly_totals.get('Expense') else [0] * num_months
    total_investment = category_monthly_totals.get('Investment').values() if category_monthly_totals.get('Investment') else [0] * num_months

    income_after_taxes = add_lists(total_income, total_tax)
    category_monthly_totals['income_after_taxes'] = income_after_taxes
    net_income = add_lists(income_after_taxes, total_expense)
    category_monthly_totals['net_income'] = net_income
    category_monthly_totals['net_cash_difference'] = add_lists(net_income, total_investment)

    return category_monthly_totals

def add_lists(list1, list2):
    if not isinstance(list1, list):
        list1 = list(list1)
    if not isinstance(list2, list):
        list2 = list(list2)
    if len(list1) != len(list2):
        return None
    length = len(list1)
    sum = []
    for ind in range(length):
        sum.append(list1[ind] + list2[ind])
    return sum

@finance.route('/income_statement')
@login_required
def income_statement():
    year = 2018
    '''
    transactions = []
    paychecks = []
    month_num = request.args.get('month', None)
    if month_num:
        month_num = int(month_num)
        days = calendar.monthrange(year, month_num)
        start_date = date(year, month_num, 1)
        end_date = date(year, month_num, days[1])

        transactions = Transaction.query.join(Account, Account.id==Transaction.account_id).filter(Account.user_id==current_user.id, Transaction.date.between(start_date, end_date)).all()
        paychecks = Paycheck.query.filter(Paycheck.user_id==current_user.id, Paycheck.date.between(start_date, end_date)).all()
    '''
    start_date = date(year, 1, 1)
    end_date = date(year, 12, 31)

    category_monthly_totals = get_category_monthly_totals(start_date, end_date)

    root_categories = Category.query.filter(Category.parent == None, Category.name.in_(['Income', 'Expense', 'Tax'])).all()

    return render_template("finance/income_statement.html",
                    root_categories=root_categories,
                    category_monthly_totals=category_monthly_totals,
                    month_choices=month_choices()
                )

@finance.route('/cash_flow')
@login_required
def cash_flow():
    year = 2018

    # transactions = []
    # paychecks = []
    # month_num = request.args.get('month', None)
    # if month_num:
    #     month_num = int(month_num)
    #     days = calendar.monthrange(year, month_num)
    #     start_date = date(year, month_num, 1)
    #     end_date = date(year, month_num, days[1])

    #     transactions = Transaction.query.join(Account, Account.id==Transaction.account_id).filter(Account.user_id==current_user.id, Transaction.date.between(start_date, end_date)).all()
    #     paychecks = Paycheck.query.filter(Paycheck.user_id==current_user.id, Paycheck.date.between(start_date, end_date)).all()

    #     paycheck_transactions = convert_paychecks_to_transactions(paychecks)
    #     transactions = transactions + paycheck_transactions

    start_date = date(year, 1, 1)
    end_date = date(year, 12, 31)

    category_monthly_totals = get_category_monthly_totals(start_date, end_date)

    #starting_balances = [account.starting_balance for account in current_user.accounts]
    #beg_bal = round(sum(starting_balances), 2)

    root_categories = Category.query.filter(Category.parent == None, Category.name == 'Investment').all()

    return render_template("finance/cash_flow.html",
                            root_categories=root_categories,
                            category_monthly_totals=category_monthly_totals,
                            #beg_bal=beg_bal,
                            month_choices=month_choices(),
                            )
