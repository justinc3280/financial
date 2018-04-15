from app import app, db
from flask import redirect, render_template, url_for
from flask_login import current_user, login_required
from app.models import Account, AccountType, Transaction, Category, Paycheck
from datetime import date

@app.route('/')
@app.route('/index')
@login_required
def index():
    return redirect(url_for('income_statement'))

@app.route('/accounts')
@login_required
def accounts():
    accounts = Account.query.all()
    return render_template('accounts.html', title='Accounts', accounts=accounts)

@app.route('/account/<int:account_id>/')
@login_required
def account_details(account_id):
    account = Account.query.filter_by(id = account_id).first_or_404()
    return render_template('account_details.html', account=account)

@app.route('/account_types')
@login_required
def account_types():
    account_types = AccountType.query.all()

    return render_template("account_types.html", account_types=account_types)


@app.route('/account/<int:account_id>/view_transactions')
@login_required
def view_transactions(account_id):
    account = Account.query.filter(Account.id == account_id).first_or_404()

    return render_template('transactions.html', transactions=account.transactions)

@app.route('/categories')
@login_required
def categories():
    categories = Category.query.all()
    return render_template('categories.html', categories=categories)

@app.route('/paychecks/')
@login_required
def paychecks():
    paychecks = Paycheck.query.filter(Paycheck.user==current_user).all()
    return render_template('paychecks.html', paychecks=paychecks)


@app.route('/balance_sheet')
@login_required
def balance_sheet():
    cash_and_equivalents = {'Total': 0}
    accounts_payable = {'Total': 0}
    for account in current_user.accounts:
        #end_date = date(month=1, day=31, year=2018)
        #end_balance = account.get_ending_balance(end_date = end_date)
        end_balance = account.get_ending_balance()
        if account.type.name == "Checking" or account.type.name == "Savings" or account.type.name == "Brokerage" or account.type.name == "Online":
            cash_and_equivalents[account.name] = round(end_balance, 2)
            cash_and_equivalents['Total'] = round(cash_and_equivalents['Total'] + end_balance, 2)
        elif account.type.name == "Credit Card":
            accounts_payable[account.name] = round(end_balance, 2)
            accounts_payable['Total'] = round(accounts_payable['Total'] + end_balance, 2)

    working_capital = cash_and_equivalents['Total'] + accounts_payable['Total']
    net_worth = working_capital

    return render_template("balance_sheet.html",
                            cash_and_equivalents=cash_and_equivalents,
                            accounts_payable=accounts_payable,
                            working_capital=working_capital,
                            net_worth=net_worth)

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
        'net_pay': 'Net Pay'
    }
    return translation[col_name]

def get_parent_categories(category):
    parent_categories = [category]
    parent_category = category.parent
    while parent_category:
        parent_categories.append(parent_category)
        parent_category = parent_category.parent
    parent_categories.reverse()
    return parent_categories

def order_dict(dictionary):
    result = {}
    for k, v in sorted(dictionary.items(), key=lambda element: element[0].rank):
        if isinstance(v, dict):
            result[k] = order_dict(v)
        else:
            result[k] = v
    return result

class Total():
    def __init__(self):
        self.rank = 0
        self.name = 'Total'

    # need to define eq and hash to use as dictionary keys
    def __eq__(self, another):
        return hasattr(another, 'name') and self.name == another.name

    def __hash__(self):
        return hash(self.name)

    def __repr__(self):
        return self.name

def category_dict(num_months=1):
    categories = Category.query.all()
    category_dict = {}
    total = Total()
    
    for category in categories:
        parent_categories = get_parent_categories(category)
        for index, category in enumerate(parent_categories):
            cat_dict = category_dict
            for x in range(0, index):
                cat_dict = cat_dict[parent_categories[x]]
            if category not in cat_dict:
                cat_dict[category] = {total: [0] * num_months}

    category_dict = order_dict(category_dict)
    return category_dict

@app.route('/income_statement')
@login_required
def income_statement():
    #transactions = Transaction.query.join(Account, Account.id==Transaction.account_id).filter(Account.user_id==current_user.id).all()
    transactions = Transaction.query.join(Account, Account.id==Transaction.account_id).filter(Account.user_id==current_user.id, Transaction.date.between('2018-02-01', '2018-02-28')).all()

    paychecks = Paycheck.query.filter(Paycheck.date.between('2018-02-01', '2018-02-28')).all()

    month_index = 0

    for paycheck in paychecks:
        paycheck_dict = paycheck.__dict__
        [paycheck_dict.pop(k) for k in ['_sa_instance_state', 'id', 'user_id', 'company_name', 'date']]

        for key, value in paycheck_dict.items():
            if key not in ['gross_pay', 'net_pay']:
                value = -value
            cat_name = paycheck_col_to_category_name(key)
            category = Category.query.filter(Category.name==cat_name).first()
            top_level_category = get_parent_categories(category)[0]
            if top_level_category.name in ["Income", "Expense", "Tax"]:
                transaction = Transaction(
                    amount = value,
                    category = category
                )
                transactions.append(transaction)
    
    categories = category_dict()
    total = Total()
    for transaction in transactions:
        parent_categories = get_parent_categories(transaction.category)
        if parent_categories[0].name in ['Income', 'Tax','Expense']:
            for index, category in enumerate(parent_categories):
                cat_dict = categories
                for x in range(0, index):
                    cat_dict = cat_dict[parent_categories[x]]
                cat_dict[category][total][month_index] += transaction.amount

    income_category = Category.query.filter(Category.name == 'Income').first()
    expense_category = Category.query.filter(Category.name == 'Expense').first()
    tax_category = Category.query.filter(Category.name == 'Tax').first()

    total_income = categories[income_category][total][0] if income_category in categories else 0
    total_expense = categories[expense_category][total][0] if expense_category in categories else 0
    total_tax = categories[tax_category][total][0] if tax_category in categories else 0

    income_after_taxes = total_income + total_tax
    net_income = income_after_taxes + total_expense

    return render_template("income_statement.html",
                            categories=categories,
                            total_object=total,
                            income_after_taxes=income_after_taxes,
                            net_income=net_income)

@app.route('/cash_flow')
@login_required
def cash_flow():
    transactions = Transaction.query.join(Account, Account.id==Transaction.account_id).filter(Account.user_id==current_user.id, Transaction.date.between('2018-02-01', '2018-02-28')).all()

    paychecks = Paycheck.query.filter(Paycheck.date.between('2018-02-01', '2018-02-28')).all()
    for paycheck in paychecks:
        paycheck_dict = paycheck.__dict__
        [paycheck_dict.pop(k) for k in ['_sa_instance_state', 'id', 'user_id', 'company_name', 'date']]

        for key, value in paycheck_dict.items():
            #cat_name = key.replace('_', ' ').title()
            cat_name = paycheck_col_to_category_name(key)
            category = Category.query.filter(Category.name==cat_name).first()
            top_level_category = get_parent_categories(category)[0]
            if top_level_category.name in ["Investment", "Transfer"]:
                transaction = Transaction(
                    amount = value,
                    category = category
                )
                transactions.append(transaction)

    categories = category_dict()
    total = Total()
    month_index = 0
    for transaction in transactions:
        parent_categories = get_parent_categories(transaction.category)
        if parent_categories[0].name in ['Investment', 'Transfer']:
            for index, category in enumerate(parent_categories):
                cat_dict = categories
                for x in range(0, index):
                    cat_dict = cat_dict[parent_categories[x]]
                cat_dict[category][total][month_index] += transaction.amount
       

    starting_balances = [account.starting_balance for account in current_user.accounts]
    beg_bal = round(sum(starting_balances), 2)

    #categories = ['Operating Activities', 'Investing Activites', 'Financing Activities', 'Total']

    sub_categories = {
        'Operating Activites': ['Net Income'],
        'Investing Activities': [],
        'Financing Activites': [],
        'Total': [] 
    }

    return render_template("cash_flow.html",
                            categories=categories,
                            beg_bal=beg_bal,
                            total_object=total
                            )
