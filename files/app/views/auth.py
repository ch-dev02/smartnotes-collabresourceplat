from datetime import datetime, timedelta
from app import app, db, models, admin, mail
from flask_admin.contrib.sqla import ModelView
from flask import render_template, request, flash, redirect, url_for, Markup
from flask_login import current_user, login_user, logout_user, login_required
from flask_mail import Message
import re
from werkzeug.security import generate_password_hash, check_password_hash
from ..forms import *
from ..scripts import *
from functools import wraps
import logging
import secrets
import socket
import os

socket.setdefaulttimeout(10)

logger = logging.getLogger(__name__)

admin.add_view(ModelView(models.User, db.session))
admin.add_view(ModelView(models.PassToken, db.session))
admin.add_view(ModelView(models.Group, db.session))
admin.add_view(ModelView(models.Member, db.session))
admin.add_view(ModelView(models.Folder, db.session))
admin.add_view(ModelView(models.Resource, db.session))
admin.add_view(ModelView(models.Review, db.session))
admin.add_view(ModelView(models.Keywords, db.session))
admin.add_view(ModelView(models.Queue, db.session))

# Decorator to check if user is logged in
def logged_out_only(func):
    @wraps(func)
    def wrap(*args, **kwargs):
        if current_user and current_user.is_authenticated:
            logger.warn('User ' + current_user.email + ' tried to access ' + request.path + ' while logged in')
            flash('You do not have access to this page!', 'danger')
            return redirect('/')
        else:
            return func(*args, **kwargs)
    return wrap

@app.route('/', methods=['GET'])
@login_required
def index():
    return render_template('index.html')

"""
Account Management Page
Loads 2 Forms
 - Change Password Form
 - Delete Account Form
Upon GET Request, renders the page with the forms
Upon POST Request
 - If change password form is submitted and validates
   - Check old password is correct
   - Check new password matches confirm password
   - Check password matches regex
   - Update password
- If change password form doesn't validate
  - Flash warning message
  - Redirect to account page 
"""
@app.route('/account', methods=['GET', 'POST'])
@login_required
def account():
    form = ChangePasswordForm()
    form2 = DeleteAccountForm()
    if request.method == 'GET':
        logger.info('User: ' + current_user.email + ' accessed account page')
        return render_template('account.html', form=form, form2=form2)
    elif form.validate_on_submit():
        # check old password is correct
        if not check_password_hash(current_user.password_hash, form.old_password.data):
            flash("Invalid Password", 'danger')
            logger.warning('User: ' + current_user.email + ' tried to change password with invalid old password')
            return redirect('/account')
        # check new password matches confirm password
        if form.new_password.data != form.confirm_password.data:
            flash("Passwords do not match", 'danger')
            logger.warning('User: ' + current_user.email + ' tried to change password with mismatched passwords')
            return redirect('/account')
        # check password matches regex
        if not valid_password(form.new_password.data):
            flash("Password must have at least 8 characters, 1 uppercase, 1 lowercase, 1 number, 1 special character", 'danger')
            logger.warning('User: ' + current_user.email + ' tried to change password with invalid new password')
            return redirect('/account')
        # update password
        current_user.password_hash = generate_password_hash(form.new_password.data)
        db.session.commit()
        logger.info('User: ' + current_user.email + ' changed password')
        flash("Password Changed", 'success')
        return redirect('/account')
    elif request.method == 'POST':
        flash("Invalid Request Detected", 'danger')
        logger.warning('User: ' + current_user.email + ' tried to access account page with invalid request')
        return redirect('/account')

"""
Route which handles the delete account form from the account page
Upon POST Request
 - If form validates
   - Check password is correct
   - Delete User Account
   - Delete any password reset tokens
   - Delete any groups they are owner of, and any linking data
   - Remove membership from any groups they are a member of
   - Delete any reviews they have made
   - Delete any resources they have uploaded and their keywords
 - If form doesn't validate
   - Flash warning message
"""
@app.route('/deleteAccount', methods=['POST'])
@login_required
def deleteAccount():
    form = DeleteAccountForm()
    if form.validate_on_submit():
        # check password is correct
        if not check_password_hash(current_user.password, form.password.data):
            flash("Invalid Password", 'danger')
            logger.warning('User: ' + current_user.email + ' tried to delete account with invalid password')
            return redirect('/account')

        logger.info('User: ' + current_user.email + ' requested account deletion')
        # delete User Account
        db.session.delete(current_user)
        # delete any password reset tokens
        models.PassToken.query.filter_by(user=current_user.id).delete()
        # delete any groups they are owner of, and any linking data
        groups = models.Group.query.filter_by(owner=current_user.id).all()
        for group in groups:
            models.Member.query.filter_by(group=group.id).delete()
            db.session.delete(group)
            # delete folders, resource, reviews, keywords associated with the group
            folders = models.Folder.query.filter_by(group=group.id).all()
            for folder in folders:
                resources = models.Resource.query.filter_by(folder=folder.id).all()
                for resource in resources:
                    models.Review.query.filter_by(resource=resource.id).delete()
                    models.Keywords.query.filter_by(resource=resource.id).delete()
                    if resource.type == "material" or resource.type == "transcript":
                        os.remove(resource.data)
                    db.session.delete(resource)
                db.session.delete(folder)
        # remove membership from any groups they are a member of
        models.Member.query.filter_by(user=current_user.id).delete()
        # delete any reviews they have made
        models.Review.query.filter_by(user=current_user.id).delete()
        # delete any resources they have uploaded and their keywords
        resources = models.Resource.query.filter_by(owner=current_user.id).all()
        for resource in resources:
            models.Keywords.query.filter_by(resource=resource.id).delete()
            if resource.type == "material" or resource.type == "transcript":
                os.remove(resource.data)
            db.session.delete(resource)
        db.session.commit()
        logout_user()
        return redirect('/')
    else:
        flash("Invalid Request Detected", 'danger')
        logger.warning('User: ' + current_user.email + ' tried to delete account with invalid form')
        return redirect('/account')

"""
Login Page
User must be logged out
GET Request
  - Renders login page and form
POST Request and form validates
  - Check all fields are filled
  - Check user exists with that email
  - Check user has verified their email
  - Check password is correct
  - Check account isn't locked
  - Lock account if too many failed attempts
  - Log user in and reset attempts
POST Request and form doesn't validate
  - Flash warning message
  - Renders login page and form
"""
@app.route('/login', methods=['GET', 'POST'])
@logged_out_only
def login(): 
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data

        # check all fields are filled
        if not email or not password:
            logger.warning('User tried to login with empty fields')
            flash("All fields are required", 'danger')
            return render_template('login.html', form=form)

        # check user exists with that email
        user = models.User.query.filter_by(email=email).first()
        if not user:
            logger.warning('User tried to login with unrecognized email')
            flash("Email or Password Incorrect", 'danger') # don't want to give away which is incorrect
            return render_template('login.html', form=form)

        if user.activated == False:
            logger.warning('User tried to login with unverified email')
            flash(Markup('Please verify your email. <a href="' + url_for('sendverify', id=user.id, _external=True) + '">Click here</a> to resend email'), 'danger')
            return render_template('login.html', form=form)

        # need to check if the account is locked or lockout is over
        if user.expire and user.expire < datetime.now():
            logger.info('User ' + user.email + ' lockout expired')
            user.locked = False
            db.session.commit()

        if user.locked:
            logger.warning('User ' + user.email + ' tried to login with locked account')
            expire_time = user.expire.strftime("%d/%m/%Y at %H:%M:%S")
            flash("Account is locked until " + expire_time, 'danger')
            return render_template('login.html', form=form)

        # check password is correct
        if not check_password_hash(user.password_hash, password):
            logger.warning('User ' + user.email + ' tried to login with incorrect password')
            # decrement login attempts
            user.attempts -= 1
            # if login attempts is 0, lock account for 10 minutes
            if(user.attempts == 0):
                logger.warning('User ' + user.email + ' locked out')
                user.locked = True
                user.attempts = 5 # reset attempts for when existing lock expires
                user.expire = datetime.now() + timedelta(minutes=10)
            db.session.commit()
            flash("Email or Password Incorrect", 'danger') # don't want to give away which is incorrect
            return render_template('login.html', form=form)

        login_user(user)
        user.attempts = 5 # reset attempts
        db.session.commit()
        logger.info('User ' + user.email + ' logged in successfully')
        flash("Login Successful", 'success')
        return redirect(url_for('index'))
    elif request.method == 'POST':
        logger.warning('User tried to login with invalid form')
        flash("Oops an error has occurred", 'danger')
        return render_template('login.html', form=form)
    else:
        logger.info("User accessed login page")
        return render_template('login.html', form=form)

"""
Sign Up Page
User must be logged out
GET Request
  - Renders sign up page and form
POST Request and form validates
  - Check all fields are filled
  - Check passwords match
  - Check terms and privacy are checked
  - Check email is not already in use
  - Check email is a valid email
  - Check password is valid
  - Create user
  - Send verification email
  - Redirect to login page
POST Request and form doesn't validate
  - Flash warning message
  - Renders sign up page and form
"""
@app.route('/signup', methods=['GET', 'POST'])
@logged_out_only
def signup():
    form = SignUpForm()
    if form.validate_on_submit():
        email = form.email.data.strip()
        password = form.password.data.strip()
        password2 = form.confirm_password.data.strip()
        terms = form.terms.data
        privacy = form.privacy.data

        # check all fields are filled and terms and privacy are checked
        if not email or not password or not password2 or not terms or not privacy:
            logger.warning('User tried to sign up with empty fields')
            flash("All fields are required", 'danger')
            return render_template('signup.html', form=form)

        # check passwords match
        if password != password2:
            logger.warning('User tried to sign up with passwords that do not match')
            flash("Passwords do not match", 'danger')
            return render_template('signup.html', form=form)

        # check email conforms to email regex and is not longer than 255 characters
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email) or len(email) > 255:
            logger.warning('User tried to sign up with invalid email')
            flash("Invalid email", 'danger')
            return render_template('signup.html', form=form)

        # check password has at least 8 characters, 1 uppercase, 1 lowercase, 1 number
        if not valid_password(password):
            logger.warning('User tried to sign up with invalid password') 
            flash("Password must have at least 8 characters, 1 uppercase, 1 lowercase, 1 number, 1 special character", 'danger')
            return render_template('signup.html', form=form) 

        # check email is not already in use
        if models.User.query.filter_by(email=email).first():
            logger.warning('User tried to sign up with email: ' + email + ' which is already in use')
            flash("Email already in use", 'danger')
            return render_template('signup.html', form=form)
        
        #hash password using werkzeug.security.generate_password_hash
        hash = generate_password_hash(password)

        # create user
        user = models.User(email=email, password_hash=hash)
        db.session.add(user)
        db.session.commit()

        logger.info('User created with email: ' + email)
        flash("Account created successfully.", 'success')
        return redirect(url_for('sendverify', id=user.id))
    elif request.method == 'POST':
        logger.warning('User tried to sign up with invalid form')
        flash("Oops an error has occurred."+str(form.errors), 'danger')
        return render_template('signup.html', form=form)
    else:
        logger.info('User loaded signup page')
        return render_template('signup.html', form=form)

"""
Reusable route to send verification email
Requires user to be logged out
GET request with id of user to send verification email to
If not id provided, redirects to login page with error
If user not found, redirects to login page with error
If user already activated, redirects to login page with error
If user found and not activated, sends verification email
"""
@app.route('/sendverify', methods=['GET'])
@logged_out_only
def sendverify():
    if not request.args.get('id'):
        logger.warning("Cannot send verification. No ID provided")
        flash("Cannot send verification. User not found", 'danger')
        return redirect(url_for('login'))
    
    id = request.args.get('id')
    user = models.User.query.filter_by(id=id).first()
    if not user:
        logger.warning("Cannot send verification. User with id " + id + " not found")
        flash("Cannot send verification. User not found", 'danger')
        return redirect(url_for('login'))
    if user.activated:
        logger.warning("Cannot send verification. User with id " + id + " already activated")
        flash("User already activated", 'danger')
        return redirect(url_for('login'))

    msg = Message('SmartNotes Email Verification', sender='smartnotesuol@gmail.com', recipients=[user.email])
    msg.body = Markup('Hello ' + user.email + ' please click the link below to verify your email address: \n\n ' + url_for('verify', id=user.id, _external=True))
    try:
        mail.send(msg)
        logger.info("Verification email sent to " + user.email)
        flash("Verification email sent", 'success')
    except:
        logger.warning("Cannot send verification. Error sending email to " + user.email)
        flash("Cannot send verification. Error sending email", 'danger')
    return redirect(url_for('login'))

"""
Verify Account Route
GET request with id parameter
id parameter is the id of the user to verify
if user is found and not activated, user is activated and redirected to login page
if user is found and activated, user is redirected to login page with error message
if user is not found, user is redirected to login page with error message
"""
@app.route('/verify', methods=['GET'])
@logged_out_only
def verify():
    if not request.args.get('id'):
        logger.warning("Cannot verify email. No ID provided")
        flash("Cannot verify email. User not found", 'danger')
        return redirect(url_for('login'))

    id = request.args.get('id')
    user = models.User.query.filter_by(id=id).first()
    if not user:
        logger.warning("Cannot verify email. User with id: " + request.args.get('id') + " not found")
        flash("Cannot verify email. User not found", 'danger')
        return redirect(url_for('login'))
    if user.activated:
        logger.warning("Cannot verify email. User with id: " + request.args.get('id') + ", already activated")
        flash("User already activated", 'danger')
        return redirect(url_for('login'))
    user.activated = True
    db.session.commit()
    logger.info("User: " + user.email + " verified email")
    flash("Email verified successfully", 'success')
    return redirect(url_for('login'))

"""
Forgot password page
User must be logged out
Upon GET request
 - User is shown the forgot password page and form
Upon POST request and form validates
 - Check user with that email exists
 - Delete any existing reset tokens
 - Create a new reset token
 - Send email to user with link to reset password
 - User is redirected to login page
Upon POST request and form does not validate
 - User is shown the forgot password page and form
 - Error messages are shown
"""
@app.route('/forgot', methods=['GET', 'POST'])
@logged_out_only
def forgot():
    form = ResetPasswordForm()
    if form.validate_on_submit():
        email = form.email.data.strip()
        user = models.User.query.filter_by(email=email).first()
        if not user:
            logger.warning("Cannot reset password. User with email: " + email + " not found")
            flash("Cannot reset password. User not found", 'danger')
            return render_template('forgot.html', form=form)
        # delete any existing reset tokens
        tokens = models.PassToken.query.filter_by(user=user.id).all()
        for token in tokens:
            db.session.delete(token)
        db.session.commit()
        msg = Message('SmartNotes Password Reset',sender='smartnotesuol@gmail.com', recipients=[user.email])
        token = secrets.token_urlsafe(32)
        while models.PassToken.query.filter_by(token=token).first():
            token = secrets.token_urlsafe(32)
        # add token to database with 24hr expiry
        expire = datetime.now() + timedelta(hours=24)
        reset = models.PassToken(user=user.id, token=token, expire=expire)
        db.session.add(reset)
        db.session.commit()
        msg.body = Markup('Hello ' + user.email + '\n\nPlease click the link below to reset your password: \n\n' + url_for('reset', id=user.id, token=token, _external=True) + '\n\nThis link will expire in 24 hours.')
        try:
            mail.send(msg)
            flash("Password reset email sent", 'success')
            logger.info("Password reset email sent to " + user.email)
        except:
            logger.warning("Cannot reset password. Error sending email to " + user.email)
            flash("Cannot reset password. Error sending email", 'danger')
        return redirect(url_for('forgot'))
    elif request.method == 'POST':
        logger.warning("Cannot reset password. Invalid form")
        flash("Cannot reset password. Invalid form", 'danger')
        return render_template('forgot.html', form=form)
    else:
        logger.info("User loaded forgot password page")
        return render_template('forgot.html', form=form)

"""
Reset password page
User must be logged out
Upon GET request
  If no id or token provided, redirect to login
  If id or token invalid, redirect to login
  If id and token valid, render reset page
Upon POST request and form validates
  If no id or token provided, redirect to login
  If id or token invalid, redirect to login
  If id and token valid, check password
  If password valid and confirm password match, update password and redirect to login
  If password invalid, render reset page
Upon POST request and form invalid
  Print error and render login page
"""
@app.route('/reset', methods=['GET', 'POST'])
@logged_out_only
def reset():
    form = ResetPasswordConfirmForm()
    if request.method == 'GET':
        if not request.args.get('id'):
            logger.warning("Cannot reset password. No ID provided")
            flash("Cannot reset password. User not found", 'danger')
            return redirect(url_for('login'))
        if not request.args.get('token'):
            logger.warning("Cannot reset password. No token provided")
            flash("Cannot reset password. User not found", 'danger')
            return redirect(url_for('login'))
        id = request.args.get('id')
        user = models.User.query.filter_by(id=id).first()
        if not user:
            logger.warning("Cannot reset password. User with id: " + id + " not found")
            flash("Cannot reset password. User not found", 'danger')
            return redirect(url_for('login'))
        token = request.args.get('token')
        reset = models.PassToken.query.filter_by(user=user.id, token=token).first()
        if not reset:
            logger.warning("Cannot reset password. Token not found")
            flash("Cannot reset password. Token not found", 'danger')
            return redirect(url_for('login'))
        if reset.expire < datetime.now():
            logger.warning("Cannot reset password. Token expired")
            flash("Cannot reset password. Token expired", 'danger')
            return redirect(url_for('login'))
        logger.info("User: " + user.email + " loaded reset password page")
        form.user_id.data = user.id
        form.token.data = token
        return render_template('reset.html', form=form)
    elif form.validate_on_submit():
        user = models.User.query.filter_by(id=form.user_id.data).first()
        if not user:
            logger.warning("Cannot reset password. User with id: " + form.user_id.data + " not found")
            flash("Cannot reset password. User not found", 'danger')
            return redirect(url_for('login'))
        reset = models.PassToken.query.filter_by(user=user.id, token=form.token.data).first()
        if not reset:
            logger.warning("Cannot reset password. Token not found")
            flash("Cannot reset password. Token not found", 'danger')
            return redirect(url_for('login'))
        if reset.expire < datetime.now():
            logger.warning("Cannot reset password. Token expired")
            flash("Cannot reset password. Token expired", 'danger')
            return redirect(url_for('login'))
        if not valid_password(form.new_password.data):
            logger.warning("Cannot reset password. Password does not meet requirements")
            flash("Cannot reset password. Password does not meet requirements", 'danger')
            return render_template('reset.html', form=form)
        if form.confirm_password.data != form.new_password.data:
            logger.warning("Cannot reset password. Passwords do not match")
            flash("Cannot reset password. Passwords do not match", 'danger')
            return render_template('reset.html', form=form)
        user.password_hash = generate_password_hash(form.new_password.data)
        db.session.delete(reset)
        db.session.commit()
        logger.info("User: " + user.email + " reset password")
        flash("Password reset successful", 'success')
        return redirect(url_for('login'))
    elif request.method == 'POST':
        logger.warning("Cannot reset password. Invalid form")
        flash("Cannot reset password. Invalid form", 'danger')
        return redirect(url_for('login'))

# Logout the User
@app.route('/logout')
@login_required
def logout():
    email = current_user.email
    logout_user()
    logger.info("User: " + email + " logged out")
    flash("Logout Successful", 'success')
    return redirect(url_for('login'))

# Privacy Policy Page
@app.route('/privacy')
def privacy():
    logger.info("User loaded privacy policy page")
    return render_template('privacy.html')

# Terms and Conditions Page
@app.route('/terms')
def terms():
    logger.info("User loaded terms and conditions page")
    return render_template('terms.html')