from app import app, db
from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user, login_required
from app.forms import LoginForm, AccountForm, AccountTypeForm, FileUploadForm, RegistrationForm, PaychecksForm
from app.models import Account, AccountType, User, FileFormat, Transaction, Category, Paycheck
from werkzeug.urls import url_parse
import csv
from datetime import datetime


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    form = LoginForm()

    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()

        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password')
            return redirect(url_for('login'))

        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get('next')
        if not next_page or url_parse(next_page).netloc != '':
            next_page = url_for('index')

        return redirect(next_page)

    return render_template('forms/login.html', title='Sign In', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('User has been logged out')
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    form = RegistrationForm()

    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('User Registered')
        return redirect(url_for('login'))
    return render_template('forms/register.html', title='Register', form=form)

@app.route('/account/<int:account_id>/edit', methods=['GET', 'POST'])
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
        if account.type:
            data['account_type'] = account.type.name
        if account.file_format:
            data['header_rows'] = account.file_format.header_rows
            data['num_columns'] = account.file_format.num_columns
            data['date_column'] = account.file_format.date_column
            data['date_format'] = account.file_format.date_format
            data['description_column'] = account.file_format.description_column
            data['amount_column'] = account.file_format.amount_column
            data['category_column'] = account.file_format.category_column

    form = AccountForm(data=data)

    if form.validate_on_submit():
        if account:
            account.name = form.name.data
        else:
            account = Account(name=form.name.data, user=current_user)
            db.session.add(account)
            db.session.commit()

        account.starting_balance = form.starting_balance.data
        account_type_name = form.account_type.data
        account.type = AccountType.query.filter(AccountType.name == account_type_name).first()
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
                header_rows = form.header_rows.data,
                num_columns = form.num_columns.data,
                date_column = form.date_column.data,
                date_format = form.date_format.data,
                description_column = form.description_column.data,
                amount_column = form.amount_column.data,
                category_column = form.category_column.data,
                account_id = account.id
            )
            db.session.add(new_format)
        db.session.commit()
        return redirect(url_for('account_details', account_id=account.id))

    return render_template('forms/edit_account.html', type=label, form=form)


@app.route('/account/<int:account_id>/delete/', methods=['GET', 'POST'])
@login_required
def delete_account(account_id):
    account = Account.query.filter(Account.id == account_id).first_or_404()
    for transaction in account.transactions:
        db.session.delete(transaction)
    db.session.delete(account.file_format)
    db.session.delete(account)
    db.session.commit()
    return redirect(url_for('accounts'))

@app.route('/add_account_type', methods=['GET', 'POST'])
@login_required
def add_account_type():
    form = AccountTypeForm()

    if form.validate_on_submit():
        account_type = AccountType(name = form.name.data, middle_level = form.middle_level.data, top_level = form.top_level.data)
        db.session.add(account_type)
        db.session.commit()
        return redirect(url_for('account_types'))

    return render_template('forms/add_account_type.html', form=form)

@app.route('/account/<int:account_id>/transactions', methods=['GET', 'POST'])
@login_required
def transactions(account_id):
    form = FileUploadForm()
    account = Account.query.filter(Account.id == account_id).first_or_404()

    if form.validate_on_submit():
        if account.file_format:
            #path = '/Users/justincianci/Documents/Financial/2018/01 - January 2018/' + form.file_upload.data
            path = '/Users/justincianci/Documents/Financial/2018/02 - February 2018/' + form.file_upload.data
            with open(path, newline='') as upload:
                data = list(csv.reader(upload, delimiter=','))
                for row in data[account.file_format.header_rows:]:
                    date_data = row[account.file_format.date_column-1]
                    if date_data == '** No Record found for the given criteria ** ':
                        continue
                    date_data = date_data[:10]

                    amount_data = row[account.file_format.amount_column-1]
                    amount_data = amount_data.replace('$', '')
                    amount_data = amount_data.replace('+', '')
                    amount_data = amount_data.replace(' ', '')

                    date = datetime.strptime(date_data, account.file_format.date_format).date()
                    description = row[account.file_format.description_column-1]
                    category_name = row[account.file_format.category_column-1] if len(row) >= account.file_format.num_columns else None
                    category = Category.query.filter(Category.name == category_name).first()
                    exists = Transaction.query.filter(Transaction.date == date, Transaction.description == description,
                                                    Transaction.amount == amount_data, Transaction.account_id == account_id).first()

                    if not exists:
                        transaction = Transaction(
                            date = date,
                            description = description,
                            amount = amount_data,
                            category = category,
                            account_id = account_id,
                        )
                        db.session.add(transaction)
                    else:
                        exists.category = category
            db.session.commit()
            return redirect(url_for('account_details', account_id=account_id ))
    return render_template('forms/file_upload.html', form=form)

@app.route('/add_categories', methods=['GET', 'POST'])
@login_required
def add_categories():
    form = FileUploadForm()

    if form.validate_on_submit():
        path = "/Users/justincianci/Documents/Development/Financial/" + form.file_upload.data
        with open(path, newline='') as upload:
            data = list(csv.reader(upload, delimiter=','))
            for row in data[1:]:
                category_name = row[0]
                parent_name = row[1] if row[1] != "None" else None
                exists = Category.query.filter(Category.name == category_name).first()
                parent_exists = Category.query.filter(Category.name == parent_name).first() if parent_name else None
                parent_category = None
                if not parent_exists:
                    if parent_name:
                        parent_category = Category(
                            name = parent_name
                        )
                        db.session.add(parent_category)
                        db.session.commit()
                if not exists:
                    category = Category(
                        name = category_name,
                        parent = parent_exists if parent_exists else parent_category,
                        rank = row[2],
                        transaction_level = (row[3] == 'TRUE')
                    )
                    db.session.add(category)
                else:
                    exists.parent = parent_exists if parent_exists else (parent_category if parent_category else None)
                    exists.rank = row[2]
                    exists.transaction_level = (row[3] == 'TRUE')
            db.session.commit()
        return redirect(url_for('categories'))

    return render_template('forms/file_upload.html', form=form)

@app.route('/add_paycheck', methods=['GET', 'POST'])
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
    company_col = 13

    if form.validate_on_submit():
        path = "/Users/justincianci/Documents/Financial/2018/Pay Statements/" + form.file_upload.data
        with open(path, newline='') as upload:
            data = list(csv.reader(upload, delimiter=','))
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
                company_name = row[company_col - 1]

                exists = Paycheck.query.filter(Paycheck.date == date, Paycheck.company_name == company_name, Paycheck.gross_pay == gross_pay, Paycheck.net_pay == net_pay).first()
                if not exists:
                    paycheck = Paycheck(
                        date = date,
                        company_name = company_name,
                        gross_pay = gross_pay,
                        federal_income_tax = federal_income_tax,
                        social_security_tax = social_security_tax,
                        medicare_tax = medicare_tax,
                        state_income_tax = state_income_tax,
                        health_insurance = health_insurance,
                        dental_insurance = dental_insurance,
                        traditional_retirement = traditional_retirement,
                        roth_retirement = roth_retirement,
                        retirement_match = retirement_match,
                        net_pay = net_pay,
                        user = current_user
                    )
                    db.session.add(paycheck)
            db.session.commit()
        return redirect(url_for('paychecks'))
    return render_template('forms/file_upload.html', form=form)
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

        return redirect(url_for('paychecks'))
    return render_template('forms/add_paycheck.html', form=form)
    '''
