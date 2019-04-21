from app import db
from flask import redirect, render_template, request, url_for
from flask_login import current_user, login_required
from app.finance import finance
from app.finance.forms import (
    AccountForm,
    AddCategoryForm,
    EditTransactionCategoryForm,
    FileUploadForm,
    PaychecksForm,
    StockTransactionForm,
)
from app.models import (
    Account,
    Category,
    FileFormat,
    Transaction,
    StockTransaction,
    Paycheck,
)
import csv
from datetime import datetime


@finance.route('/account/<int:account_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_account(account_id):
    if account_id > 0:
        account = Account.query.filter(Account.id == account_id).first()
        label = "Edit"
    else:
        account = None
        label = "Create"

    data = {}
    if account:
        data['name'] = account.name
        data['starting_balance'] = account.starting_balance
        if account.category:
            data['account_category'] = account.category.id
        if account.file_format:
            data['header_rows'] = account.file_format.header_rows
            data['num_columns'] = account.file_format.num_columns
            data['date_column'] = account.file_format.date_column
            data['date_format'] = account.file_format.date_format
            data['description_column'] = account.file_format.description_column
            data['amount_column'] = account.file_format.amount_column
            data['category_column'] = account.file_format.category_column

    form = AccountForm(data=data)
    root_categories = Category.query.filter(
        Category.parent == None, Category.name.in_(['Assetts', 'Liabilities'])
    ).all()
    categories = []
    for category in root_categories:
        categories.extend(category.get_transaction_level_children())
    form.account_category.choices = [(0, 'None')] + sorted(
        [(category.id, category.name) for category in categories], key=lambda x: x[1]
    )

    if request.form:
        if account:
            account.name = form.name.data
        else:
            account = Account(name=form.name.data, user=current_user)
            db.session.add(account)
            db.session.commit()

        account.starting_balance = form.starting_balance.data
        account.category_id = form.account_category.data
        if account.file_format:
            account.file_format.header_rows = form.header_rows.data
            account.file_format.num_columns = form.num_columns.data
            account.file_format.date_column = form.date_column.data
            account.file_format.date_format = form.date_format.data
            account.file_format.description_column = form.description_column.data
            account.file_format.amount_column = form.amount_column.data
            account.file_format.category_column = form.category_column.data
        else:
            new_format = FileFormat(
                header_rows=form.header_rows.data,
                num_columns=form.num_columns.data,
                date_column=form.date_column.data,
                date_format=form.date_format.data,
                description_column=form.description_column.data,
                amount_column=form.amount_column.data,
                category_column=form.category_column.data,
                account_id=account.id,
            )
            db.session.add(new_format)
        db.session.commit()
        return redirect(url_for('finance.account_details', account_id=account.id))

    return render_template('finance/forms/edit_account.html', type=label, form=form)


@finance.route('/account/<int:account_id>/delete/', methods=['GET', 'POST'])
@login_required
def delete_account(account_id):
    account = Account.query.filter(Account.id == account_id).first_or_404()
    for transaction in account.transactions:
        db.session.delete(transaction)
    db.session.delete(account.file_format)
    db.session.delete(account)
    db.session.commit()
    return redirect(url_for('finance.accounts'))


@finance.route('/account/<int:account_id>/transactions', methods=['GET', 'POST'])
@login_required
def transactions(account_id):
    form = FileUploadForm()
    account = Account.query.filter(Account.id == account_id).first_or_404()

    if form.validate_on_submit():
        if account.file_format:
            file_contents = form.file_upload.data.read().decode('utf-8').splitlines()
            data = list(csv.reader(file_contents, delimiter=','))
            # combine these queries
            uncategorized_expense_category = Category.query.filter(
                Category.name == "Uncategorized Expense"
            ).first()
            uncategorized_income_category = Category.query.filter(
                Category.name == "Other Income"
            ).first()

            if (
                len(data[account.file_format.header_rows])
                < account.file_format.category_column
            ):
                category_defined = False

            for row in data[account.file_format.header_rows :]:
                date_data = row[account.file_format.date_column - 1]
                if date_data in [
                    '** No Record found for the given criteria ** ',
                    '***END OF FILE***',
                ]:
                    continue
                date = datetime.strptime(
                    date_data, account.file_format.date_format
                ).date()

                amount_data = row[account.file_format.amount_column - 1]
                amount_data = amount_data.replace('$', '')
                amount_data = amount_data.replace('+', '')
                amount_data = amount_data.replace(' ', '')
                amount_data = amount_data.replace(',', '')

                description = row[account.file_format.description_column - 1]
                if (
                    len(data[account.file_format.header_rows])
                    >= account.file_format.category_column
                ):
                    category_name = row[account.file_format.category_column - 1]
                    category_obj = Category.query.filter(
                        Category.name == category_name
                    ).first()
                    category = (
                        category_obj
                        if category_obj
                        else (
                            uncategorized_expense_category
                            if float(amount_data) < 0
                            else uncategorized_income_category
                        )
                    )
                else:
                    category = (
                        uncategorized_expense_category
                        if float(amount_data) < 0
                        else uncategorized_income_category
                    )

                transaction = Transaction.query.filter(
                    Transaction.date == date,
                    Transaction.description == description,
                    Transaction.amount == amount_data,
                    Transaction.account_id == account_id,
                ).first()

                if not transaction:
                    transaction = Transaction(
                        date=date,
                        description=description,
                        amount=amount_data,
                        category=category,
                        account_id=account_id,
                    )
                    db.session.add(transaction)
            db.session.commit()
        return redirect(url_for('finance.account_details', account_id=account_id))
    return render_template('finance/forms/file_upload.html', form=form)


@finance.route(
    '/transaction/<int:transaction_id>/edit_category', methods=['GET', 'POST']
)
@login_required
def edit_transaction_category(transaction_id):
    transaction = Transaction.query.get_or_404(transaction_id)

    if request.form:
        new_category_id = int(request.form.get('category'))
        transaction.category_id = new_category_id
        db.session.commit()
        return transaction.category.name

    form = EditTransactionCategoryForm(data={'category': transaction.category.id})
    categories = Category.query.all()
    form.category.choices = [
        (category.id, category.name)
        for category in categories
        if category.is_transaction_level
        and category.top_level_parent().name
        in [
            ('Expense' if transaction.amount < 0 else 'Income'),
            'Transfer',
            'Investment',
        ]
    ]

    return render_template(
        'finance/forms/edit_transaction_category.html',
        form=form,
        transaction=transaction,
    )


@finance.route('/add_category', methods=['GET', 'POST'])
@login_required
def add_category():
    form = AddCategoryForm()
    categories = Category.query.all()
    form.parent.choices = [(0, 'None')] + sorted(
        [(category.id, category.name) for category in categories], key=lambda x: x[1]
    )

    if request.form:
        if form.parent.data:
            parent_category = Category.query.get_or_404(form.parent.data)
            new_rank = len(parent_category.children)
            db.session.add(
                Category(name=form.name.data, parent_id=form.parent.data, rank=new_rank)
            )
        else:
            new_rank = Category.num_root_categories() + 1
            db.session.add(Category(name=form.name.data, rank=new_rank))
        db.session.commit()

    return render_template('finance/forms/add_category.html', form=form)


@finance.route('/add_paycheck', methods=['GET', 'POST'])
@login_required
def add_paycheck():
    form = FileUploadForm()

    date_col = 1
    gross_pay_col = 2
    fed_tax_col = 3
    ss_tax_col = 4
    med_tax_col = 5
    state_tax_col = 6
    dental_col = 7
    health_col = 8
    traditional_ret_col = 9
    roth_ret_col = 10
    net_pay_col = 11
    ret_match_col = 12
    gtl_col = 13
    gym_reimbursement_col = 14
    company_col = 15
    espp_col = 16

    if form.validate_on_submit():
        file_contents = form.file_upload.data.read().decode('utf-8').splitlines()
        data = list(csv.reader(file_contents, delimiter=','))
        for row in data[1:]:
            date = row[date_col - 1]
            date = datetime.strptime(date, '%m/%d/%Y').date()
            gross_pay = row[gross_pay_col - 1]
            federal_income_tax = row[fed_tax_col - 1]
            social_security_tax = row[ss_tax_col - 1]
            medicare_tax = row[med_tax_col - 1]
            state_income_tax = row[state_tax_col - 1]
            dental_insurance = row[dental_col - 1]
            health_insurance = row[health_col - 1]
            traditional_retirement = row[traditional_ret_col - 1]
            roth_retirement = row[roth_ret_col - 1]
            net_pay = row[net_pay_col - 1]
            retirement_match = row[ret_match_col - 1]
            gtl = float(row[gtl_col - 1])
            gym_reimbursement = float(row[gym_reimbursement_col - 1])
            company_name = row[company_col - 1]
            espp = float(row[espp_col - 1])

            exists = Paycheck.query.filter(
                Paycheck.date == date,
                Paycheck.company_name == company_name,
                Paycheck.gross_pay == gross_pay,
                Paycheck.net_pay == net_pay,
            ).first()
            if not exists:
                paycheck = Paycheck(
                    date=date,
                    company_name=company_name,
                    gross_pay=gross_pay,
                    federal_income_tax=federal_income_tax,
                    social_security_tax=social_security_tax,
                    medicare_tax=medicare_tax,
                    state_income_tax=state_income_tax,
                    health_insurance=health_insurance,
                    dental_insurance=dental_insurance,
                    traditional_retirement=traditional_retirement,
                    roth_retirement=roth_retirement,
                    retirement_match=retirement_match,
                    net_pay=net_pay,
                    user=current_user,
                )
                other_fields = {}
                if gtl:
                    other_fields['gtl'] = gtl
                if gym_reimbursement:
                    other_fields['gym_reimbursement'] = gym_reimbursement
                if espp:
                    other_fields['espp'] = espp
                paycheck.update_properties(other_fields)
                db.session.add(paycheck)

        db.session.commit()
        return redirect(url_for('finance.paychecks'))
    return render_template('finance/forms/file_upload.html', form=form)
    '''
    form = PaychecksForm()

    if form.validate_on_submit():
        paycheck = Paycheck(
            date = datetime.strptime(form.date.data, '%m/%d/%Y').date(),
            company_name = form.company_name.data,
            gross_pay = form.gross_pay.data,
            federal_income_tax = form.federal_income_tax.data,
            social_security_tax = form.social_security_tax.data,
            medicare_tax = form.medicare_tax.data,
            state_income_tax = form.state_income_tax.data,
            health_insurance = form.health_insurance.data,
            dental_insurance = form.dental_insurance.data,
            traditional_retirement = form.traditional_retirement.data,
            roth_retirement = form.roth_retirement.data,
            retirement_match = form.retirement_match.data,
            net_pay = form.net_pay.data,
            user = current_user
        )
        db.session.add(paycheck)
        db.session.commit()

        return redirect(url_for('finance.paychecks'))
    return render_template('finance/forms/add_paycheck.html', form=form)
    '''


@finance.route('/stock_transaction/<int:transaction_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_stock_transaction(transaction_id):
    if transaction_id > 0:
        stock_transaction = Transaction.query.get(transaction_id)
        label = "Edit"
    else:
        stock_transaction = None
        label = "Add"

    data = {}
    if stock_transaction:
        properties = stock_transaction.get_properties()
        data['transaction_type'] = stock_transaction.category.name
        data['date'] = stock_transaction.date
        data['symbol'] = properties.get('symbol')
        data['quantity'] = properties.get('quantity')
        data['transaction_fee'] = properties.get('transaction_fee')
        data['cost_basis'] = properties.get('cost_basis')
        data['split_adjustment'] = properties.get('split_adjustment')

    form = StockTransactionForm(data=data)

    category_choices = (
        db.session.query(Category.id, Category.name)
        .filter(Category.name.in_(['Buy', 'Sell']))
        .all()
    )

    buy_category_id = next(
        (category.id for category in category_choices if category.name == 'Buy')
    )
    sell_category_id = next(
        (category.id for category in category_choices if category.name == 'Sell')
    )

    if form.validate_on_submit():
        selected_category_id = (
            sell_category_id
            if form.transaction_type.data == "Sell"
            else buy_category_id
        )

        if stock_transaction:
            stock_transaction.date = form.date.data
            stock_transaction.category_id = selected_category_id
        else:
            stock_transaction = Transaction(
                date=form.date.data, category_id=selected_category_id, user=current_user
            )
            db.session.add(stock_transaction)

        properties = {
            'symbol': form.symbol.data,
            'quantity': form.quantity.data,
            'transaction_fee': form.transaction_fee.data,
        }
        if form.cost_basis.data:
            properties['cost_basis'] = form.cost_basis.data
        if form.split_adjustment.data:
            properties['split_adjustment'] = form.split_adjustment.data
        stock_transaction.update_properties(properties)

        db.session.commit()
        return redirect(url_for('finance.stock_transactions'))
    return render_template(
        'finance/forms/edit_stock_transaction.html', type=label, form=form
    )
