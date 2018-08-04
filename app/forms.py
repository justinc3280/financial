from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SelectField, SubmitField, FileField
from flask_wtf.file import FileAllowed, FileRequired
from wtforms.validators import DataRequired, Email, EqualTo, ValidationError
from app.models import User

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    password2 = PasswordField(
        'Repeat Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Register')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user is not None:
            raise ValidationError('Username not available')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user is not None:
            raise ValidationError('Email address already registered')

class AccountForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    starting_balance = StringField('Starting Balance')
    header_rows = StringField('Number of Header Rows')
    num_columns = StringField('Number of Columns')
    date_column = StringField('Date Column')
    date_format = SelectField('Date Format', choices=[('%m/%d/%Y', 'MM/DD/YYYY'), ('%m/%d/%y', 'MM/DD/YY'), ('%Y-%m-%d', 'YYYY-MM-DD'), ('%Y-%m-%dT%H:%M:%S', 'YYYY-MM-DDTHH:MM:SS')])
    description_column = StringField('Description Column')
    amount_column = StringField('Amount Column')
    category_column = StringField('Category Column')
    account_type = StringField('Account Type')
    submit = SubmitField('Submit')

class AccountTypeForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    middle_level = StringField('Middle Level', validators=[DataRequired()])
    top_level = StringField('Top Level', validators=[DataRequired()])
    submit = SubmitField('Submit')

class FileUploadForm(FlaskForm):
    file_upload = FileField('File')
    submit = SubmitField('Submit')

class EditCategoryForm(FlaskForm):
    category = SelectField('Select Category', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Submit')

class PaychecksForm(FlaskForm):
    date = StringField('Date', validators=[DataRequired()])
    company_name = StringField('Company', validators=[DataRequired()])
    gross_pay = StringField('Gross Pay', validators=[DataRequired()])
    federal_income_tax = StringField('Federal Income Tax', validators=[DataRequired()])
    social_security_tax = StringField('Social Security Tax', validators=[DataRequired()])
    medicare_tax = StringField('Medicare Tax', validators=[DataRequired()])
    state_income_tax = StringField('State Income Tax', validators=[DataRequired()])
    health_insurance = StringField('Health Insurance', validators=[DataRequired()])
    dental_insurance = StringField('Dental Insurance', validators=[DataRequired()])
    traditional_retirement = StringField('Traditional Retirement', validators=[DataRequired()])
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
