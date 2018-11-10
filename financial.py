from app import db, create_app
from app.models import Account, Transaction, User

app = create_app()

@app.shell_context_processor
def make_shell_context():
    return {
        'db': db,
        'User': User,
        'Transaction': Transaction,
        'Account': Account
    }
