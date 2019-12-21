import json

from app import db
from flask_login import UserMixin
from datetime import date
from app import login
from werkzeug.security import generate_password_hash, check_password_hash


@login.user_loader
def load_user(id):
    return User.query.get(int(id))


class Properties:
    properties = db.Column(db.Text, default="{}")

    def get_properties(self):
        if self.properties:
            return json.loads(str(self.properties))
        else:
            return {}

    def get_property(self, name, default=None):
        return self.get_properties().get(name, default)

    def set_properties(self, properties):
        self.properties = json.dumps(properties)

    def update_properties(self, data):
        current_properties = self.get_properties()
        current_properties.update(data)
        self.set_properties(current_properties)

    def remove_property(self, key):
        current_properties = self.get_properties()
        current_properties.pop(key, None)
        self.set_properties(current_properties)


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True)
    email = db.Column(db.String(120), index=True, unique=True)
    password_hash = db.Column(db.String(128))
    accounts = db.relationship('Account', backref='user')
    paychecks = db.relationship('Paycheck', backref='user', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_api_repr(self):
        return {'id': self.id, 'username': self.username, 'email': self.email}

    def __repr__(self):
        return '<User {}>'.format(self.username)


class Transaction(db.Model, Properties):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date)
    description = db.Column(db.String(240))
    amount = db.Column(db.Float)
    category_id = db.Column(db.Integer, db.ForeignKey("category.id"))
    category = db.relationship('Category')
    account_id = db.Column(db.Integer, db.ForeignKey("account.id"))

    def __repr__(self):
        return '<Transaction- date: {}, amount: {}, description: {}>'.format(
            self.date, self.amount, self.description
        )


class Account(db.Model, Properties):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64))
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    transactions = db.relationship('Transaction', backref='account')
    starting_balance = db.Column(db.Float)
    category_id = db.Column(db.Integer, db.ForeignKey("category.id"))
    category = db.relationship('Category')

    def __repr__(self):
        return '<Account {}>'.format(self.name)

    def get_file_format(self):
        return self.get_property('file_format')

    def update_file_format(
        self,
        header_rows,
        num_columns,
        date_column,
        date_format,
        description_column,
        amount_column,
        category_column,
    ):
        format_data = {
            'file_format': {
                'header_rows': int(header_rows),
                'num_columns': int(num_columns),
                'date_column': int(date_column),
                'date_format': date_format,
                'description_column': int(description_column),
                'amount_column': int(amount_column),
                'category_column': int(category_column),
            }
        }
        self.update_properties(format_data)

    def get_ending_balance(self, end_date=None):
        today = date.today()
        if end_date and end_date > today:
            return 0  # return something else
        ending_balance = self.starting_balance
        for transaction in self.transactions:
            if end_date and transaction.date > end_date:
                continue
            ending_balance += transaction.amount
        return ending_balance


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64))
    parent_id = db.Column(db.Integer, db.ForeignKey("category.id"))
    rank = db.Column(db.Integer)
    category_type = db.Column(db.String(64))

    parent = db.relationship('Category', remote_side=[id])
    children = db.relationship('Category')

    @classmethod
    def num_root_categories(cls):
        return cls.query.filter(Category.parent == None).count()

    @property
    def is_transaction_level(self):
        return self.parent and not bool(self.children)

    def top_level_parent(self):
        return self.get_parent_categories()[0]

    def get_parent_categories(self):
        parent_categories = [self]
        parent_category = self.parent
        while parent_category:
            parent_categories.append(parent_category)
            parent_category = parent_category.parent
        parent_categories.reverse()
        return parent_categories

    def get_transaction_level_children(self):
        transaction_level_children = []
        for child_category in self.children:
            if child_category.is_transaction_level:
                transaction_level_children.append(child_category)
            else:
                transaction_level_children.extend(
                    child_category.get_transaction_level_children()
                )
        return transaction_level_children

    def __repr__(self):
        return '<Category {}>'.format(self.name)


class Paycheck(db.Model, Properties):
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
