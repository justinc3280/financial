import argparse
import sys
import os

if os.path.abspath(os.curdir) not in sys.path:
    print('...missing directory in PYTHONPATH... added!')
    sys.path.append(os.path.abspath(os.curdir))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models as m

parser = argparse.ArgumentParser(description='Migrate SQLite to MYSQL')
parser.add_argument('--host', required=True)
parser.add_argument('--user', required=True)
parser.add_argument('--password', required=True)
parser.add_argument('--dbname', required=True)
args = parser.parse_args()

SQLITE_DBNAME = 'app.db'
sqlite_uri = 'sqlite:///' + SQLITE_DBNAME
sqlite_engine = create_engine(sqlite_uri, echo=False)
sqlite_session = sessionmaker(bind=sqlite_engine)()

mysql_uri = 'mysql+pymysql://{}:{}@{}/{}'.format(
    args.user, args.password, args.host, args.dbname
)
print('Connecting to database at {}'.format(mysql_uri))
mysql_engine = create_engine(mysql_uri, echo=False)
mysql_session = sessionmaker(bind=mysql_engine)()

mysql_session.query(m.Transaction).delete()
mysql_session.query(m.Paycheck).delete()
mysql_session.query(m.FileFormat).delete()
mysql_session.query(m.Account).delete()
mysql_session.query(m.User).delete()

for category in mysql_session.query(m.Category):
    category.parent_id = None
    mysql_session.delete(category)
mysql_session.flush()

users = []
for user in sqlite_session.query(m.User):
    users.append(
        m.User(
            id=user.id,
            username=user.username,
            email=user.email,
            password_hash=user.password_hash,
        )
    )
mysql_session.add_all(users)
mysql_session.flush()

categories = []
category_parent_ids = {}
for category in sqlite_session.query(m.Category):
    category_parent_ids[category.id] = category.parent_id
    categories.append(
        m.Category(
            id=category.id,
            name=category.name,
            # parent_id=category.parent_id,
            rank=category.rank,
            category_type=category.category_type,
        )
    )
mysql_session.add_all(categories)
mysql_session.flush()

# add parent_ids after flushing to prevent foreign key contraint failures
# sqlalchemy.exc.IntegrityError: (pymysql.err.IntegrityError)
# (1452, 'Cannot add or update a child row: a foreign key constraint fails
for category in categories:
    category.parent_id = category_parent_ids.get(category.id)
mysql_session.flush()

accounts = []
for account in sqlite_session.query(m.Account):
    accounts.append(
        m.Account(
            id=account.id,
            name=account.name,
            user_id=account.user_id,
            starting_balance=account.starting_balance,
            category_id=account.category_id,
        )
    )
mysql_session.add_all(accounts)
mysql_session.flush()

file_formats = []
for file_format in sqlite_session.query(m.FileFormat):
    file_formats.append(
        m.FileFormat(
            id=file_format.id,
            header_rows=file_format.header_rows,
            num_columns=file_format.num_columns,
            date_column=file_format.date_column,
            date_format=file_format.date_format,
            description_column=file_format.description_column,
            amount_column=file_format.amount_column,
            category_column=file_format.category_column,
            account_id=file_format.account_id,
        )
    )
mysql_session.add_all(file_formats)
mysql_session.flush()

paychecks = []
for paycheck in sqlite_session.query(m.Paycheck):
    paychecks.append(
        m.Paycheck(
            id=paycheck.id,
            date=paycheck.date,
            company_name=paycheck.company_name,
            gross_pay=paycheck.gross_pay,
            federal_income_tax=paycheck.federal_income_tax,
            social_security_tax=paycheck.social_security_tax,
            medicare_tax=paycheck.medicare_tax,
            state_income_tax=paycheck.state_income_tax,
            health_insurance=paycheck.health_insurance,
            dental_insurance=paycheck.dental_insurance,
            traditional_retirement=paycheck.traditional_retirement,
            roth_retirement=paycheck.roth_retirement,
            retirement_match=paycheck.retirement_match,
            net_pay=paycheck.net_pay,
            user_id=paycheck.user_id,
            properties=paycheck.properties,
        )
    )
mysql_session.add_all(paychecks)
mysql_session.flush()

transactions = []
for transaction in sqlite_session.query(m.Transaction):
    transactions.append(
        m.Transaction(
            id=transaction.id,
            date=transaction.date,
            description=transaction.description,
            amount=transaction.amount,
            category_id=transaction.category_id,
            account_id=transaction.account_id,
            properties=transaction.properties,
        )
    )
mysql_session.add_all(transactions)
mysql_session.flush()

sqlite_session.close()
mysql_session.commit()
mysql_session.close()

print('Data transfer complete')
print('{} users transfered'.format(len(users)))
print('{} categories transfered'.format(len(categories)))
print('{} file_formats transfered'.format(len(file_formats)))
print('{} accounts transfered'.format(len(accounts)))
print('{} paychecks transfered'.format(len(paychecks)))
print('{} transactions transfered'.format(len(transactions)))
