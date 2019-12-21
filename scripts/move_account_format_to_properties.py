import sys
import os

if os.path.abspath(os.curdir) not in sys.path:
    sys.path.append(os.path.abspath(os.curdir))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Account, FileFormat

SQLITE_DBNAME = 'app.db'
sqlite_uri = 'sqlite:///' + SQLITE_DBNAME
sqlite_engine = create_engine(sqlite_uri, echo=False)
session = sessionmaker(bind=sqlite_engine)()

for file_format in session.query(FileFormat):
    format_data = {
        'file_format': {
            'header_rows': file_format.header_rows,
            'num_columns': file_format.num_columns,
            'date_column': file_format.date_column,
            'date_format': file_format.date_format,
            'description_column': file_format.description_column,
            'amount_column': file_format.amount_column,
            'category_column': file_format.category_column
        }
    }
    account = session.query(Account).get(file_format.account_id)
    account.update_properties(format_data)

session.commit()
session.close()
