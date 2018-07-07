from app import db
from flask_login import UserMixin
from app import login
from werkzeug.security import generate_password_hash, check_password_hash

@login.user_loader
def load_user(id):
    return User.query.get(int(id))

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True)
    email = db.Column(db.String(120), index=True, unique=True)
    password_hash = db.Column(db.String(128))
    accounts = db.relationship('Account', backref='user', lazy='dynamic')
    paychecks = db.relationship('Paycheck', backref='user', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return '<User {}>'.format(self.username)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date)
    description = db.Column(db.String(120))
    amount = db.Column(db.Float)
    category_id = db.Column(db.Integer, db.ForeignKey("category.id"))
    category = db.relationship('Category')
    account_id = db.Column(db.Integer, db.ForeignKey("account.id"))

    def __repr__(self):
        return '<Transaction- date: {}, amount: {}, description: {}>'.format(self.date, self.amount, self.description)

class FileFormat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    header_rows = db.Column(db.Integer)
    num_columns = db.Column(db.Integer)
    date_column = db.Column(db.Integer)
    date_format = db.Column(db.String(60))
    description_column = db.Column(db.Integer)
    amount_column = db.Column(db.Integer)
    category_column = db.Column(db.Integer)
    account_id = db.Column(db.Integer, db.ForeignKey("account.id"))
    account = db.relationship('Account')

class Account(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64))
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    file_format = db.relationship('FileFormat', uselist=False)
    transactions = db.relationship('Transaction', backref='account', lazy='dynamic')
    starting_balance = db.Column(db.Float)
    type_id = db.Column(db.Integer, db.ForeignKey("account_type.id"))
    type = db.relationship('AccountType')

    def __repr__(self):
        return '<Account {}>'.format(self.name)

    def get_ending_balance(self, end_date=None):
        ending_balance = self.starting_balance
        for transaction in self.transactions:
            if end_date and transaction.date > end_date:
                continue
            ending_balance += transaction.amount
        return ending_balance

class AccountType(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64))
    middle_level = db.Column(db.String(64))
    top_level = db.Column(db.String(64))

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64))
    parent_id = db.Column(db.Integer, db.ForeignKey("category.id"))
    rank = db.Column(db.Integer)
    transaction_level = db.Column(db.Boolean)

    parent = db.relationship('Category', remote_side=[id])
    children = db.relationship('Category')

    def top_level_parent(self):
        if self.parent is None:
            return self
        return self.parent.top_level_parent()

    def __repr__(self):
        return '<Category {}>'.format(self.name)

class Paycheck(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date)
    company_name = db.Column(db.String(64))
    gross_pay = db.Column(db.Float)
    federal_income_tax = db.Column(db.Float)
    social_security_tax = db.Column(db.Float)
    medicare_tax = db.Column(db.Float)
    state_income_tax = db.Column(db.Float)
    health_insurance = db.Column(db.Float)
    dental_insurance = db.Column(db.Float)
    traditional_retirement = db.Column(db.Float)
    roth_retirement = db.Column(db.Float)
    retirement_match = db.Column(db.Float)
    net_pay = db.Column(db.Float)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))

    def __repr__(self):
        return '<Paycheck {}>'.format(self.date)
