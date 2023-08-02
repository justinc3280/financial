import csv
from datetime import datetime

from flask import redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import db
from app.finance import finance
from app.finance.forms import (
    AccountForm,
    AddCategoryForm,
    EditTransactionCategoryForm,
    FileUploadForm,
    PaychecksForm,
)
from app.models import Account, Category, Transaction, Paycheck


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

        account_file_format = account.get_file_format()
        if account_file_format:
            data['header_rows'] = account_file_format['header_rows']
            data['num_columns'] = account_file_format['num_columns']
            data['date_column'] = account_file_format['date_column']
            data['date_format'] = account_file_format['date_format']
            data['description_column'] = account_file_format['description_column']
            data['amount_column'] = account_file_format['amount_column']
            data['category_column'] = account_file_format['category_column']

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

        account.starting_balance = form.starting_balance.data
        account.category_id = form.account_category.data

        account.update_file_format(
            form.header_rows.data,
            form.num_columns.data,
            form.date_column.data,
            form.date_format.data,
            form.description_column.data,
            form.amount_column.data,
            form.category_column.data,
        )
        db.session.commit()
        return redirect(url_for('finance.account_details', account_id=account.id))

    return render_template('finance/forms/edit_account.html', type=label, form=form)


@finance.route('/account/<int:account_id>/delete/', methods=['GET', 'POST'])
@login_required
def delete_account(account_id):
    account = Account.query.filter(Account.id == account_id).first_or_404()
    # Transactions should be handled by a cascade delete
    for transaction in account.transactions:
        db.session.delete(transaction)
    db.session.delete(account)
    db.session.commit()
    return redirect(url_for('finance.accounts'))


@finance.route('/account/<int:account_id>/transactions', methods=['GET', 'POST'])
@login_required
def transactions(account_id):
    form = FileUploadForm()
    account = Account.query.filter(Account.id == account_id).first_or_404()

    if form.validate_on_submit():
        account_file_format = account.get_file_format()
        if account_file_format:
            file_contents = form.file_upload.data.read().decode('utf-8').splitlines()
            data = list(csv.reader(file_contents, delimiter=','))
            # combine these queries
            uncategorized_expense_category = Category.query.filter(
                Category.name == "Uncategorized Expense"
            ).first()
            uncategorized_income_category = Category.query.filter(
                Category.name == "Other Income"
            ).first()

            if account_id == 10:
                options_premium_received_category = Category.query.filter(
                    Category.name == "Options Premium"
                ).first()
                options_premium_paid_category = Category.query.filter(
                    Category.name == "Options Premium Paid"
                ).first()

            for row in data[account_file_format['header_rows'] :]:
                if not row:
                    continue

                date_data = row[account_file_format['date_column'] - 1]
                date_data = date_data.strip()
                if date_data in [
                    '',
                    '** No Record found for the given criteria **',
                    '***END OF FILE***',
                ] or date_data.startswith('Total activity from'):
                    continue

                date = datetime.strptime(
                    date_data, account_file_format['date_format']
                ).date()

                # TODO: make this configurable in DB
                amount_needs_invert = False
                if account_id in [14, 15, 16]:
                    # American Express, Apple Card, and Capital One accounts needs amount inverted
                    amount_needs_invert = True

                amount_data = row[account_file_format['amount_column'] - 1]
                if account_id == 14 and amount_data is '':
                    # Capital Ones credit column is after the debit column
                    amount_data = row[account_file_format['amount_column']]
                    # Credits don't need to be inverted
                    amount_needs_invert = False

                amount_data = amount_data.replace('$', '')
                amount_data = amount_data.replace('+', '')
                amount_data = amount_data.replace(' ', '')
                amount_data = amount_data.replace(',', '')
                amount_data = float(amount_data)

                if amount_needs_invert:
                    amount_data = -amount_data

                description = row[account_file_format['description_column'] - 1]
                description = description.strip()

                # Merrill Edge ignore cash sweeps
                if account_id == 12 and (description.startswith('Deposit ML') or description.startswith('Withdrawal ML')):
                    continue

                # TD Ameritrade ignore cash sweeps
                if account_id == 10:
                    if description.startswith('CASH ALTERNATIVES PURCHASE') or description.startswith('CASH ALTERNATIVES REDEMPTION'):
                        continue
                    elif description.startswith('CASH ALTERNATIVES INTEREST'):
                        # Interest amount is in the quantity column to the right of the description column
                        amount_data = float(row[account_file_format['description_column']])

                if (
                    len(data[account_file_format['header_rows']])
                    >= account_file_format['category_column']
                ):
                    category_name = row[account_file_format['category_column'] - 1]
                    category_obj = Category.query.filter(
                        Category.name == category_name
                    ).first()
                    category = (
                        category_obj
                        if category_obj
                        else (
                            uncategorized_expense_category
                            if amount_data < 0
                            else uncategorized_income_category
                        )
                    )
                else:
                    category = None
                    if account_id == 10:
                        if description.startswith('Sold'):
                            category = options_premium_received_category
                        elif description.startswith('Bought'):
                            category = options_premium_paid_category

                    if category is None:
                        category = (
                            uncategorized_expense_category
                            if amount_data < 0
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
            'Expense',
            'Income',
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
    ma_pfml_tax_col = 6
    state_tax_col = 7
    dental_col = 8
    health_col = 9
    fsa_col = 10
    traditional_ret_col = 11
    roth_ret_col = 12
    net_pay_col = 13
    ret_match_col = 14
    std_col = 15
    transit_col = 16
    company_col = 17
    gtl_col = None
    gym_reimbursement_col = None
    expense_reimbursement_col = None
    espp_col = None

    if form.validate_on_submit():
        file_contents = form.file_upload.data.read().decode('utf-8').splitlines()
        data = list(csv.reader(file_contents, delimiter=','))
        for row in data[1:]:
            date = row[date_col - 1]
            date = datetime.strptime(date, '%m/%d/%Y').date()
            gross_pay = row[gross_pay_col - 1]
            federal_income_tax = row[fed_tax_col - 1]
            ma_pfml_tax = float(row[ma_pfml_tax_col - 1])
            social_security_tax = row[ss_tax_col - 1]
            medicare_tax = row[med_tax_col - 1]
            state_income_tax = row[state_tax_col - 1]
            dental_insurance = row[dental_col - 1]
            health_insurance = row[health_col - 1]
            fsa = float(row[fsa_col - 1])
            traditional_retirement = row[traditional_ret_col - 1]
            roth_retirement = row[roth_ret_col - 1]
            net_pay = row[net_pay_col - 1]
            retirement_match = row[ret_match_col - 1]
            std = float(row[std_col - 1])
            transit = float(row[transit_col - 1])
            gtl = float(row[gtl_col - 1]) if gtl_col else None
            gym_reimbursement = float(row[gym_reimbursement_col - 1]) if gym_reimbursement_col else None
            expense_reimbursement = float(row[expense_reimbursement_col - 1]) if expense_reimbursement_col else None
            company_name = row[company_col - 1]
            espp = float(row[espp_col - 1]) if espp_col else None

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
                if expense_reimbursement:
                    other_fields['expense_reimbursement'] = expense_reimbursement
                if espp:
                    other_fields['espp'] = espp
                if fsa:
                    other_fields['fsa'] = fsa
                if ma_pfml_tax:
                    other_fields['ma_pfml_tax'] = ma_pfml_tax
                if std:
                    other_fields['std'] = std
                if transit:
                    other_fields['transit'] = transit
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
