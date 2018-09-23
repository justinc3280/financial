"""update category table

Revision ID: 46eb887b7d62
Revises: c5e38d91af2a
Create Date: 2018-02-25 21:07:36.733202

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '46eb887b7d62'
down_revision = 'c5e38d91af2a'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('account_type',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=64), nullable=True),
    sa.Column('middle_level', sa.String(length=64), nullable=True),
    sa.Column('top_level', sa.String(length=64), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('category',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=64), nullable=True),
    sa.Column('parent_id', sa.Integer(), nullable=True),
    sa.Column('rank', sa.Integer(), nullable=True),
    sa.Column('transaction_level', sa.Boolean(), nullable=True),
    sa.ForeignKeyConstraint(['parent_id'], ['category.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('account',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=64), nullable=True),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('starting_balance', sa.Float(), nullable=True),
    sa.Column('type_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['type_id'], ['account_type.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('paycheck',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('date', sa.Date(), nullable=True),
    sa.Column('company_name', sa.String(length=64), nullable=True),
    sa.Column('gross_pay', sa.Float(), nullable=True),
    sa.Column('federal_income_tax', sa.Float(), nullable=True),
    sa.Column('social_security_tax', sa.Float(), nullable=True),
    sa.Column('medicare_tax', sa.Float(), nullable=True),
    sa.Column('state_income_tax', sa.Float(), nullable=True),
    sa.Column('health_insurance', sa.Float(), nullable=True),
    sa.Column('dental_insurance', sa.Float(), nullable=True),
    sa.Column('traditional_retirement', sa.Float(), nullable=True),
    sa.Column('roth_retirement', sa.Float(), nullable=True),
    sa.Column('retirement_match', sa.Float(), nullable=True),
    sa.Column('net_pay', sa.Float(), nullable=True),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('file_format',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('header_rows', sa.Integer(), nullable=True),
    sa.Column('num_columns', sa.Integer(), nullable=True),
    sa.Column('date_column', sa.Integer(), nullable=True),
    sa.Column('date_format', sa.String(length=60), nullable=True),
    sa.Column('description_column', sa.Integer(), nullable=True),
    sa.Column('amount_column', sa.Integer(), nullable=True),
    sa.Column('category_column', sa.Integer(), nullable=True),
    sa.Column('account_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['account_id'], ['account.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('transaction',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('date', sa.Date(), nullable=True),
    sa.Column('description', sa.String(length=120), nullable=True),
    sa.Column('amount', sa.Float(), nullable=True),
    sa.Column('category_id', sa.Integer(), nullable=True),
    sa.Column('account_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['account_id'], ['account.id'], ),
    sa.ForeignKeyConstraint(['category_id'], ['category.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('transaction')
    op.drop_table('file_format')
    op.drop_table('paycheck')
    op.drop_table('account')
    op.drop_table('category')
    op.drop_table('account_type')
    # ### end Alembic commands ###
