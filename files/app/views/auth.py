from app import app, db, models, admin, mail
from flask_admin.contrib.sqla import ModelView
from flask import render_template, request, flash, redirect, url_for, Markup
from flask_login import current_user
from flask_mail import Message
import re
from werkzeug.security import generate_password_hash
from ..forms import *
from ..scripts import *
from functools import wraps
import logging
import socket

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

@app.route('/login', methods=['GET', 'POST'])
@logged_out_only
def login():
    return redirect(url_for('index'))

@app.route('/', methods=['GET', 'POST'])
def index():
    return render_template('index.html')

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