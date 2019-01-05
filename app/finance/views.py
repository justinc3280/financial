from app import db
from app.finance import finance
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

@finance.route('/stocks')
@login_required
def stocks():
    return render_template("finance/stocks.html")

@finance.route('/stock_transactions')
@login_required
def stock_transactions():
    stock_transactions = StockTransaction.query.filter(StockTransaction.user==current_user).all()

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
    # currently only works if start and end date are in the same year. TODO: Fix
    num_months = end_date.month - start_date.month + 1

    ending_month_dates = []
    for month_num in range(start_date.month, end_date.month + 1):
        last_day = calendar.monthrange(start_date.year, month_num)[1]
        ending_month_dates.append(date(start_date.year, month_num, last_day))

    accounts_monthly_ending_balance = {}
    for account in current_user.accounts: #maybe pass in user or accounts to make this function predictable
        ending_balances = {index: account.get_ending_balance(date) for index, date in enumerate(ending_month_dates)}
        accounts_monthly_ending_balance[account.name] = ending_balances

        parent_categories = account.category.get_parent_categories() if account.category else []
        for parent in parent_categories:
            if parent.name not in accounts_monthly_ending_balance:
                accounts_monthly_ending_balance[parent.name] = {index: total for index, total in enumerate([0] * num_months)}
            update_category_balances = add_lists(accounts_monthly_ending_balance.get(parent.name).values(), ending_balances.values())
            accounts_monthly_ending_balance[parent.name] = {index: total for index, total in enumerate(update_category_balances)}

    total_current_assetts = accounts_monthly_ending_balance.get('Current Assetts', {index: total for index, total in enumerate([0] * num_months)})
    total_current_liabilities = accounts_monthly_ending_balance.get('Current Liabilities', {index: total for index, total in enumerate([0] * num_months)})
    accounts_monthly_ending_balance['working_capital'] = add_lists(total_current_assetts.values(), total_current_liabilities.values())

    total_assetts = accounts_monthly_ending_balance.get('Assetts', {index: total for index, total in enumerate([0] * num_months)})
    total_liabilities = accounts_monthly_ending_balance.get('Liabilities', {index: total for index, total in enumerate([0] * num_months)})
    accounts_monthly_ending_balance['net_worth'] = add_lists(total_assetts.values(), total_liabilities.values())


    transactions = Transaction.query.join(Account, Account.id==Transaction.account_id).filter(Account.user_id==current_user.id, Transaction.date.between(start_date, end_date)).all()
    paychecks = Paycheck.query.filter(Paycheck.user_id==current_user.id, Paycheck.date.between(start_date, end_date)).all()

    paycheck_transactions = convert_paychecks_to_transactions(paychecks)
    transactions.extend(paycheck_transactions)

    category_monthly_totals = {}
    category_monthly_totals.update(accounts_monthly_ending_balance)
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

@finance.route('/balance_sheet')
@login_required
def balance_sheet():
    year = 2018
    start_date = date(year, 1, 1)
    end_date = date(year, 12, 31)

    current_monthly_totals = get_category_monthly_totals(start_date, end_date)
    summary_row_items = [('Working Capital', 'working_capital'), ('Net Worth', 'net_worth')]

    root_categories = Category.query.filter(Category.parent == None, Category.name.in_(['Assetts', 'Liabilities'])).all()
    
    return render_template("finance/financial_statement.html",
                            root_categories=root_categories,
                            category_monthly_totals=current_monthly_totals,
                            summary_row_items=summary_row_items,
                            month_choices=month_choices())

@finance.route('/income_statement')
@login_required
def income_statement():
    year = 2018
    '''
    month_num = request.args.get('month', None)
    if month_num:
        month_num = int(month_num)
        days = calendar.monthrange(year, month_num)
        start_date = date(year, month_num, 1)
        end_date = date(year, month_num, days[1])
    '''
    start_date = date(year, 1, 1)
    end_date = date(year, 12, 31)

    category_monthly_totals = get_category_monthly_totals(start_date, end_date)
    summary_row_items = [('Income After Taxes', 'income_after_taxes'), ('Net Income', 'net_income')]

    root_categories = Category.query.filter(Category.parent == None, Category.name.in_(['Income', 'Expense', 'Tax'])).all()

    return render_template("finance/financial_statement.html",
                    page_title='Income Statement',
                    root_categories=root_categories,
                    category_monthly_totals=category_monthly_totals,
                    summary_row_items=summary_row_items,
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

    start_date = date(year, 1, 1)
    end_date = date(year, 12, 31)

    category_monthly_totals = get_category_monthly_totals(start_date, end_date)
    header_row_items = [('Net Income', 'net_income')]
    summary_row_items = [('Net Cash Difference', 'net_cash_difference')]

    root_categories = Category.query.filter(Category.parent == None, Category.name == 'Investment').all()

    return render_template("finance/financial_statement.html",
                            page_title='Cash Flow Statement',
                            root_categories=root_categories,
                            category_monthly_totals=category_monthly_totals,
                            header_row_items=header_row_items,
                            summary_row_items=summary_row_items,
                            month_choices=month_choices(),
                            )
