from app import db
from app.finance import finance
from flask import redirect, render_template, request, url_for
from flask_login import current_user, login_required
from app.models import Account, Category, Paycheck, StockTransaction, Transaction
from datetime import date
import calendar
from collections import defaultdict
from sqlalchemy.orm import aliased, joinedload
from app.finance.accounts import AccountManager
from app.finance.charts import generate_chart
from app.finance.stocks import Stocks


def get_accounts():
    return (
        Account.query.filter(Account.user == current_user)
        .options(joinedload(Account.transactions), joinedload(Account.category))
        .all()
    )


@finance.route('/')
@finance.route('/index')
@login_required
def index():
    return redirect(url_for('finance.balance_sheet'))


@finance.route('/accounts')
@login_required
def accounts():
    accounts = Account.query.filter(Account.user == current_user).all()
    return render_template('finance/accounts.html', title='Accounts', accounts=accounts)


@finance.route('/account/<int:account_id>/')
@login_required
def account_details(account_id):
    account = Account.query.filter_by(id=account_id).first_or_404()
    return render_template('finance/account_details.html', account=account)


@finance.route('/stocks')
@login_required
def stocks():

    account_manager = AccountManager(get_accounts())
    stocks_data = account_manager.get_current_stock_holdings()

    return render_template("finance/stocks.html", stock_data=stocks_data)


@finance.route('/stock_transactions')
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
        "finance/stock_transactions.html", stock_transactions=stock_transactions
    )


@finance.route('/account/<int:account_id>/view_transactions')
@login_required
def view_transactions(account_id):
    account = Account.query.filter(Account.id == account_id).first_or_404()
    return render_template(
        'finance/transactions.html', transactions=list(account.transactions)
    )


@finance.route('/categories')
@login_required
def categories():
    root_categories = Category.query.filter(Category.parent == None).all()
    return render_template('finance/categories.html', categories=root_categories)


@finance.route('/paychecks')
@login_required
def paychecks():
    paychecks = Paycheck.query.filter(Paycheck.user == current_user).all()
    return render_template('finance/paychecks.html', paychecks=paychecks)


def month_choices():
    choices = []
    for i, month in enumerate(calendar.month_name):
        if i == 0:
            month = "Select Month"
        choices.append((i, month))
    return choices


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
        'retirement_match_in': '401K Match In',
        'gtl': 'G.T.L.',
        'gtl_in': 'G.T.L. In',
        #'gym_reimbursement': 'Gym Reimbursement',
        'gym_reimbursement': 'Other Income',
        'fsa': 'FSA Contribution',
        'net_pay': 'Net Pay',
        'expense_reimbursement': 'Expense Reimbursement',
        'espp': 'ESPP Refunded',
    }
    return translation[col_name]


def convert_paychecks_to_transactions(paychecks):
    transactions = []
    for paycheck in paychecks:
        paycheck_dict = paycheck.__dict__
        paycheck_date = paycheck_dict.get('date')
        for key, value in paycheck.get_properties().items():
            paycheck_dict[key] = value
            if key in ['gtl', 'retirement_match']:
                paycheck_dict['{}_in'.format(key)] = value

        [
            paycheck_dict.pop(k)
            for k in [
                '_sa_instance_state',
                'id',
                'user_id',
                'company_name',
                'date',
                'properties',
            ]
        ]

        for key, value in paycheck_dict.items():
            if key not in [
                'gross_pay',
                'net_pay',
                'gym_reimbursement',
                'expense_reimbursement',
                'gtl_in',
                'retirement_match_in',
            ]:
                value = -value
            cat_name = paycheck_col_to_category_name(key)
            category = Category.query.filter(Category.name == cat_name).first()
            top_level_category = category.top_level_parent()
            if top_level_category.name in ['Income', 'Expense', 'Tax', 'Investment']:
                transaction = Transaction(
                    amount=value, date=paycheck_date, category=category
                )
                transactions.append(transaction)
    return transactions


def initialized_category_data(num_months):
    return {index: total for index, total in enumerate([0] * num_months, start=1)}


def get_accounts_category_monthly_balances(year):
    def list_to_dict(list):
        return {i: data for i, data in enumerate(list, start=1)}

    current_date = date.today()
    num_months = 12 if year < current_date.year else current_date.month

    account_manager = AccountManager(current_user.accounts)
    account_ending_balances = account_manager.get_accounts_monthly_ending_balances_for_year(
        year
    )

    accounts_monthly_ending_balance = {}

    for account_name, ending_balances in account_ending_balances.items():
        accounts_monthly_ending_balance[account_name] = list_to_dict(ending_balances)

    accounts_monthly_ending_balance['Stocks (Market Value)'] = list_to_dict(
        account_manager.get_stocks_monthly_market_values(year)
    )

    for (
        account
    ) in (
        current_user.accounts
    ):  # maybe pass in user or accounts to make this function predictable
        ending_balances = accounts_monthly_ending_balance.get(account.name)
        if ending_balances:
            parent_categories = (
                account.category.get_parent_categories() if account.category else []
            )
            for parent in parent_categories:
                if parent.name not in accounts_monthly_ending_balance:
                    accounts_monthly_ending_balance[
                        parent.name
                    ] = initialized_category_data(num_months)
                accounts_monthly_ending_balance[parent.name] = add_dict_totals(
                    accounts_monthly_ending_balance.get(parent.name), ending_balances
                )

    total_current_assetts = accounts_monthly_ending_balance.get(
        'Current Assetts', initialized_category_data(num_months)
    )
    total_current_liabilities = accounts_monthly_ending_balance.get(
        'Current Liabilities', initialized_category_data(num_months)
    )
    accounts_monthly_ending_balance['Working Capital'] = add_dict_totals(
        total_current_assetts, total_current_liabilities
    )

    total_assetts = accounts_monthly_ending_balance.get(
        'Assetts', initialized_category_data(num_months)
    )
    total_liabilities = accounts_monthly_ending_balance.get(
        'Liabilities', initialized_category_data(num_months)
    )
    accounts_monthly_ending_balance['Net Worth'] = add_dict_totals(
        total_assetts, total_liabilities
    )

    return accounts_monthly_ending_balance


def get_category_monthly_totals(start_date, end_date):
    # currently only works if start and end date are in the same year. TODO: Fix
    num_months = end_date.month - start_date.month + 1

    transactions = (
        Transaction.query.join(Account, Account.id == Transaction.account_id)
        .filter(
            Account.user_id == current_user.id,
            Transaction.date.between(start_date, end_date),
        )
        .all()
    )
    paychecks = Paycheck.query.filter(
        Paycheck.user_id == current_user.id, Paycheck.date.between(start_date, end_date)
    ).all()

    paycheck_transactions = convert_paychecks_to_transactions(paychecks)
    transactions.extend(paycheck_transactions)

    category_monthly_totals = {}
    for transaction in transactions:
        parent_categories = transaction.category.get_parent_categories()
        for parent_category in parent_categories:
            if parent_category.name not in category_monthly_totals:
                category_monthly_totals[
                    parent_category.name
                ] = initialized_category_data(num_months)
            category_monthly_totals[parent_category.name][
                transaction.date.month
            ] += transaction.amount

    total_income = category_monthly_totals.get(
        'Income', initialized_category_data(num_months)
    )
    total_tax = category_monthly_totals.get(
        'Tax', initialized_category_data(num_months)
    )
    total_expense = category_monthly_totals.get(
        'Expense', initialized_category_data(num_months)
    )
    total_investment = category_monthly_totals.get(
        'Investment', initialized_category_data(num_months)
    )

    category_monthly_totals[
        'Income After Taxes'
    ] = income_after_taxes = add_dict_totals(total_income, total_tax)
    category_monthly_totals['Net Income'] = net_income = add_dict_totals(
        income_after_taxes, total_expense
    )
    category_monthly_totals['Net Cash Difference'] = add_dict_totals(
        net_income, total_investment
    )

    return category_monthly_totals


def add_dict_totals(dict1, dict2):
    total = {}
    for key, value1 in dict1.items():
        value2 = dict2.get(key, 0)
        total[key] = value1 + value2
    return total


@finance.route('/balance_sheet')
@login_required
def balance_sheet():
    year = int(request.args.get('year', date.today().year))

    current_monthly_totals = get_accounts_category_monthly_balances(year)

    root_categories = Category.query.filter(
        Category.parent == None, Category.name.in_(['Assetts', 'Liabilities'])
    ).all()

    return render_template(
        "finance/financial_statement.html",
        year=year,
        page_title='{} Balance Sheet'.format(year),
        root_categories=root_categories,
        category_monthly_totals=current_monthly_totals,
        summary_row_items=['Working Capital', 'Net Worth'],
        month_choices=month_choices(),
    )


@finance.route('/income_statement')
@login_required
def income_statement():
    year = int(request.args.get('year', date.today().year))
    start_date = date(year, 1, 1)
    end_date = date(year, 12, 31)

    category_monthly_totals = get_category_monthly_totals(start_date, end_date)

    root_categories = Category.query.filter(
        Category.parent == None, Category.name.in_(['Income', 'Expense', 'Tax'])
    ).all()

    return render_template(
        "finance/financial_statement.html",
        year=year,
        page_title='{} Income Statement'.format(year),
        root_categories=root_categories,
        category_monthly_totals=category_monthly_totals,
        summary_row_items=['Income After Taxes', 'Net Income'],
        month_choices=month_choices(),
    )


@finance.route('/cash_flow')
@login_required
def cash_flow():
    year = int(request.args.get('year', date.today().year))
    start_date = date(year, 1, 1)
    end_date = date(year, 12, 31)

    category_monthly_totals = get_category_monthly_totals(start_date, end_date)

    root_categories = Category.query.filter(
        Category.parent == None, Category.name == 'Investment'
    ).all()

    return render_template(
        "finance/financial_statement.html",
        page_title='{} Cash Flow Statement'.format(year),
        year=year,
        root_categories=root_categories,
        category_monthly_totals=category_monthly_totals,
        header_row_items=['Net Income'],
        summary_row_items=['Net Cash Difference'],
        month_choices=month_choices(),
    )


@finance.route('/category/<int:category_id>/month/<int:month>/year/<int:year>')
@login_required
def get_transactions_for_category(category_id, month, year):
    start_date = date(year, month, 1)
    last_day = calendar.monthrange(start_date.year, month)[1]
    end_date = date(year, month, last_day)
    category = Category.query.get(category_id)

    data = None
    if category.category_type == 'transaction':
        if category.is_transaction_level:
            transactions_q = Transaction.query.filter(
                Transaction.category_id == category_id
            )
        else:
            children_category_ids = [
                category.id for category in category.get_transaction_level_children()
            ]
            transactions_q = Transaction.query.filter(
                Transaction.category_id.in_(children_category_ids)
            )

        data = transactions_q.filter(
            Transaction.date.between(start_date, end_date)
        ).all()

    elif category.category_type == 'account':
        accounts = Account.query.filter(Account.category_id == category_id).all()
        data = {
            account.name: account.get_ending_balance(end_date) for account in accounts
        }

    return render_template(
        'finance/transactions_for_category.html',
        month=calendar.month_name[month],
        year=year,
        category=category,
        data=data,
    )


def get_plotting_data_for_category(data):
    months = []
    amounts = []
    for month_num, amount in data.items():
        months.append(calendar.month_abbr[month_num])
        amounts.append(abs(amount))
    return months, amounts


@finance.route('/charts/')
@finance.route(
    '/charts/<string:category_name>/'
)  # don't like because includes accounts and other non-category things
@login_required
def charts(category_name=None):
    year = 2018
    start_date = date(year, 1, 1)
    end_date = date(year, 12, 31)

    charts = []
    category_monthly_totals = get_category_monthly_totals(start_date, end_date)
    if category_name:
        category_data = category_monthly_totals.get(category_name)
        if category_data:
            months, amounts = get_plotting_data_for_category(category_data)
            charts.append(
                generate_chart(months, amounts, title='2018 {}'.format(category_name))
            )
    else:
        income_data = category_monthly_totals.get('Income')
        income_months, income_amounts = get_plotting_data_for_category(income_data)
        charts.append(
            generate_chart(income_months, income_amounts, title='2018 Income')
        )

        expense_data = category_monthly_totals.get('Expense')
        months, amounts = get_plotting_data_for_category(expense_data)
        charts.append(generate_chart(months, amounts, title='2018 Expenses'))

    return render_template('finance/charts.html', charts=charts)


@finance.route('/stocks/return/data')
@login_required
def stocks_return_data():
    year = int(request.args.get('year', date.today().year))

    account_manager = AccountManager(get_accounts())

    data = account_manager.get_brokerage_roi_data(year)
    monthly_data = data.get('monthly_data')
    annual_return = data.get('annual_return')

    return render_template(
        'finance/return_data.html',
        year=year,
        data=monthly_data,
        annual_return=annual_return,
    )


@finance.route('/stocks/return/')
@login_required
def stocks_return():
    year = int(request.args.get('year', date.today().year))

    account_manager = AccountManager(get_accounts())

    total_roi_data = account_manager.get_brokerage_compounded_roi(2011, year)

    return render_template('finance/return.html', year=year, data=total_roi_data)

