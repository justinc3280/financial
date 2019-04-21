from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    DateField,
    FileField,
    FloatField,
    SelectField,
    StringField,
    SubmitField,
)
from flask_wtf.file import FileAllowed, FileRequired
from wtforms.validators import DataRequired, Optional


class AccountForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    starting_balance = StringField('Starting Balance')
    header_rows = StringField('Number of Header Rows')
    num_columns = StringField('Number of Columns')
    date_column = StringField('Date Column')
    date_format = SelectField(
        'Date Format',
        choices=[
            ('%m/%d/%Y', 'MM/DD/YYYY'),
            ('%m/%d/%y', 'MM/DD/YY'),
            ('%Y-%m-%d', 'YYYY-MM-DD'),
            ('%Y-%m-%dT%H:%M:%S', 'YYYY-MM-DDTHH:MM:SS'),
        ],
    )
    description_column = StringField('Description Column')
    amount_column = StringField('Amount Column')
    category_column = StringField('Category Column')
    account_category = SelectField('Account Category', coerce=int)


class FileUploadForm(FlaskForm):
    file_upload = FileField('File')
    submit = SubmitField('Submit')


class AddCategoryForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    parent = SelectField('Parent Category', coerce=int, validators=[DataRequired()])


class EditTransactionCategoryForm(FlaskForm):
    category = SelectField('Category', coerce=int, validators=[DataRequired()])


class PaychecksForm(FlaskForm):
    date = StringField('Date', validators=[DataRequired()])
    company_name = StringField('Company', validators=[DataRequired()])
    gross_pay = StringField('Gross Pay', validators=[DataRequired()])
    federal_income_tax = StringField('Federal Income Tax', validators=[DataRequired()])
    social_security_tax = StringField(
        'Social Security Tax', validators=[DataRequired()]
    )
    medicare_tax = StringField('Medicare Tax', validators=[DataRequired()])
    state_income_tax = StringField('State Income Tax', validators=[DataRequired()])
    health_insurance = StringField('Health Insurance', validators=[DataRequired()])
    dental_insurance = StringField('Dental Insurance', validators=[DataRequired()])
    traditional_retirement = StringField(
        'Traditional Retirement', validators=[DataRequired()]
    )
    roth_retirement = StringField('Roth Retirement', validators=[DataRequired()])
    retirement_match = StringField('Retirement Match', validators=[DataRequired()])
    net_pay = StringField('Net Pay', validators=[DataRequired()])
    submit = SubmitField('Submit')
    '''
    def validate_net_pay(self):
        return self.net_pay == (self.gross_pay - self.federal_income_tax -
                    self.social_security_tax - self.medicare_tax - self.state_income_tax -
                    self.health_insurance - self.dental_insurance - self.traditional_retirement -
                    self.roth_retirement
                )
    '''


class StockTransactionForm(FlaskForm):
    date = DateField('Date', validators=[DataRequired()], format='%m/%d/%Y')
    symbol = StringField('Symbol', validators=[DataRequired()])
    quantity = FloatField('Quantity', validators=[DataRequired()])
    cost_basis = FloatField('Cost Basis', validators=[Optional()])
    transaction_fee = FloatField('Fee')
    transaction_type = SelectField(
        'Type', choices=[('Buy', 'Buy'), ('Sell', 'Sell')], validators=[DataRequired()]
    )
    split_adjustment = FloatField('Stock Split Adjustment', validators=[Optional()])
    submit = SubmitField('Submit')

    # def validate_cost_basis(form, field):
    #     if form.transaction_type.data == 'sell' and not field.data:
    #         raise ValidationError('Name must be less than 50 characters')
