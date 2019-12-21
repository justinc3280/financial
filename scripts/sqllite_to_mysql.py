import argparse
import sys
import os

if os.path.abspath(os.curdir) not in sys.path:
    sys.path.append(os.path.abspath(os.curdir))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models as m

parser = argparse.ArgumentParser(description='Migrate data to new database')
parser.add_argument('--host', help='MySQL host', required=True)
parser.add_argument('--user', help='MySQL user', required=True)
parser.add_argument('--password', help='MySQL password', required=True)
parser.add_argument('--dbname', help='MySQL db name', required=True)
parser.add_argument('--sqlitedb', help='Name of sqlite database')
parser.add_argument(
    '--tosqlite', help='Set to send data to sqlite', action='store_true'
)
args = parser.parse_args()

SQLITE_DBNAME = args.sqlitedb or 'app.db'
sqlite_uri = 'sqlite:///' + SQLITE_DBNAME
sqlite_engine = create_engine(sqlite_uri, echo=False)

mysql_uri = 'mysql+pymysql://{}:{}@{}/{}'.format(
    args.user, args.password, args.host, args.dbname
)
print('Connecting to MySQL database at {}'.format(mysql_uri))
mysql_engine = create_engine(mysql_uri, echo=False)

if args.tosqlite:
    source_session = sessionmaker(bind=mysql_engine)()
    destination_session = sessionmaker(bind=sqlite_engine)()
    print('Transfering data from MySQL to Sqlite database')
else:
    source_session = sessionmaker(bind=sqlite_engine)()
    destination_session = sessionmaker(bind=mysql_engine)()
    print('Transfering data from Sqlite to MySQL database')

# Delete data from destination database
destination_session.query(m.Transaction).delete()
destination_session.query(m.Paycheck).delete()
destination_session.query(m.Account).delete()
destination_session.query(m.User).delete()

for category in destination_session.query(m.Category):
    category.parent_id = None
    destination_session.delete(category)
destination_session.flush()

users = []
for user in source_session.query(m.User):
    users.append(
        m.User(
            id=user.id,
            username=user.username,
            email=user.email,
            password_hash=user.password_hash,
        )
    )
destination_session.add_all(users)
destination_session.flush()

categories = []
category_parent_ids = {}
for category in source_session.query(m.Category):
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
destination_session.add_all(categories)
destination_session.flush()

# add parent_ids after flushing to prevent foreign key contraint failures
# sqlalchemy.exc.IntegrityError: (pymysql.err.IntegrityError)
# (1452, 'Cannot add or update a child row: a foreign key constraint fails
for category in categories:
    category.parent_id = category_parent_ids.get(category.id)
destination_session.flush()

accounts = []
for account in source_session.query(m.Account):
    accounts.append(
        m.Account(
            id=account.id,
            name=account.name,
            user_id=account.user_id,
            starting_balance=account.starting_balance,
            category_id=account.category_id,
            properties=account.properties,
        )
    )
destination_session.add_all(accounts)
destination_session.flush()

paychecks = []
for paycheck in source_session.query(m.Paycheck):
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
destination_session.add_all(paychecks)
destination_session.flush()

transactions = []
for transaction in source_session.query(m.Transaction):
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
destination_session.add_all(transactions)
destination_session.flush()

source_session.close()
destination_session.commit()
destination_session.close()

print('Data transfer complete')
print('{} users transfered'.format(len(users)))
print('{} categories transfered'.format(len(categories)))
print('{} accounts transfered'.format(len(accounts)))
print('{} paychecks transfered'.format(len(paychecks)))
print('{} transactions transfered'.format(len(transactions)))
