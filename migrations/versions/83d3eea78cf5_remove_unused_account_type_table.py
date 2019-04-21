"""remove unused account type table

Revision ID: 83d3eea78cf5
Revises: b3e641d7c3de
Create Date: 2019-04-21 07:40:27.645538

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '83d3eea78cf5'
down_revision = 'b3e641d7c3de'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('account_type')
    op.drop_constraint(None, 'account', type_='foreignkey')
    op.create_foreign_key(None, 'account', 'category', ['category_id'], ['id'])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'account', type_='foreignkey')
    op.create_foreign_key(None, 'account', 'account_type', ['type_id'], ['id'])
    op.create_table('account_type',
    sa.Column('id', sa.INTEGER(), nullable=False),
    sa.Column('name', sa.VARCHAR(length=64), nullable=True),
    sa.Column('middle_level', sa.VARCHAR(length=64), nullable=True),
    sa.Column('top_level', sa.VARCHAR(length=64), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###
