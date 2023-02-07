from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, HiddenField, FileField, TextAreaField, IntegerField
from wtforms.validators import DataRequired, NumberRange

class SignUpForm(FlaskForm):
    email = StringField('email', validators=[DataRequired()])
    password = PasswordField('password', validators=[DataRequired()])
    confirm_password = PasswordField('confirm_password', validators=[DataRequired()])
    terms = BooleanField('terms', validators=[DataRequired()])
    privacy = BooleanField('privacy', validators=[DataRequired()])

