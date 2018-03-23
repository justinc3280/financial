from app import app, db
from app.models import Account, Transaction, User

@app.shell_context_processor
def make_shell_context():
    return {
        'db': db,
        'User': User,
        'Transaction': Transaction,
        'Account': Account
        }
