from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, HiddenField, FileField, TextAreaField, IntegerField
from wtforms.validators import DataRequired, NumberRange

class LoginForm(FlaskForm):
    email = StringField('email', validators=[DataRequired()])
    password = PasswordField('password', validators=[DataRequired()])

class SignUpForm(FlaskForm):
    email = StringField('email', validators=[DataRequired()])
    password = PasswordField('password', validators=[DataRequired()])
    confirm_password = PasswordField('confirm_password', validators=[DataRequired()])
    terms = BooleanField('terms', validators=[DataRequired()])
    privacy = BooleanField('privacy', validators=[DataRequired()])

class ChangePasswordForm(FlaskForm):
    old_password = PasswordField('old_password', validators=[DataRequired()])
    new_password = PasswordField('new_password', validators=[DataRequired()])
    confirm_password = PasswordField('confirm_password', validators=[DataRequired()])

class ResetPasswordForm(FlaskForm):
    email = StringField('email', validators=[DataRequired()])

class ResetPasswordConfirmForm(FlaskForm):
    user_id = HiddenField('user_id', validators=[DataRequired()])
    token = HiddenField('token', validators=[DataRequired()])
    new_password = PasswordField('new_password', validators=[DataRequired()])
    confirm_password = PasswordField('confirm_password', validators=[DataRequired()])

class DeleteAccountForm(FlaskForm):
    password = PasswordField('password', validators=[DataRequired()])

class CreateGroupForm(FlaskForm):
    title = StringField('title', validators=[DataRequired()])

class JoinGroupForm(FlaskForm):
    code = StringField('code', validators=[DataRequired()])

class DelLeaveGroupForm(FlaskForm):
    group_id = HiddenField('group_id', validators=[DataRequired()])

class CreateFolderForm(FlaskForm):
    title = StringField('title', validators=[DataRequired()])
    group_id = HiddenField('group_id', validators=[DataRequired()])

class DelFolderForm(FlaskForm):
    folder_id = HiddenField('folder_id', validators=[DataRequired()])

class AddURLForm(FlaskForm):
    title = StringField('title', validators=[DataRequired()])
    url = StringField('url', validators=[DataRequired()])

class UploadFileForm(FlaskForm):
    title = StringField('title', validators=[DataRequired()])
    file = FileField('file', validators=[DataRequired()])

class NotesForm(FlaskForm):
    title = StringField('title', validators=[DataRequired()])
    notes = TextAreaField('notes')

class DelResourceForm(FlaskForm):
    resource_id = HiddenField('resource_id', validators=[DataRequired()])

class ReviewForm(FlaskForm):
    resource_id = HiddenField('resource_id', validators=[DataRequired()])
    review = TextAreaField('review', validators=[DataRequired()])
    rating = IntegerField('rating', validators=[DataRequired(), NumberRange(min=0, max=5)])

class DelReviewForm(FlaskForm):
    review_id = HiddenField('review_id', validators=[DataRequired()])

class GenerateKeywordsForm(FlaskForm):
    resource_id = HiddenField('resource_id', validators=[DataRequired()])