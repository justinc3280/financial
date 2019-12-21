"""add account properties

Revision ID: 5b27c108546b
Revises: 1bebd86b652e
Create Date: 2019-12-21 17:09:18.748264

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5b27c108546b'
down_revision = '1bebd86b652e'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('account', schema=None) as batch_op:
        batch_op.add_column(sa.Column('properties', sa.Text(), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('account', schema=None) as batch_op:
        batch_op.drop_column('properties')

    # ### end Alembic commands ###