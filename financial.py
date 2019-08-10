from app import db, create_app
from app.models import Account, Transaction, User

import decimal
import flask.json


class MyJSONEncoder(flask.json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, decimal.Decimal) or isinstance(obj, float):
            # Convert decimal instances to strings.
            return str(round(obj, 2))
        return super(MyJSONEncoder, self).default(obj)


app = create_app()
app.json_encoder = MyJSONEncoder


@app.shell_context_processor
def make_shell_context():
    return {'db': db, 'User': User, 'Transaction': Transaction, 'Account': Account}
