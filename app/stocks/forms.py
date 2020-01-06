from flask_wtf import FlaskForm
from wtforms import FloatField, StringField
from wtforms.validators import DataRequired, Optional


class StockTransactionForm(FlaskForm):
    symbol = StringField('Symbol', validators=[DataRequired()])
    quantity = FloatField('Quantity', validators=[DataRequired()])
    cost_basis = FloatField('Cost Basis', validators=[DataRequired()])
    transaction_fee = FloatField('Fee', validators=[DataRequired()])
    split_adjustment = FloatField('Stock Split Adjustment', validators=[Optional()])
    market_value = FloatField('Market Value', validators=[Optional()])
