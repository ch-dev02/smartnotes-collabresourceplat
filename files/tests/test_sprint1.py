import pytest
import os
os.environ["TESTING"] = "1"
from app import app as flask_app, db, models, mail
del os.environ["TESTING"]
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from flask_mail import Mail
import logging

@pytest.fixture(scope="session")
def app():
    flask_app.config['TESTING'] = True
    flask_app.config['WTF_CSRF_ENABLED'] = False
    flask_app.logger.disabled = True
    log = logging.getLogger(__name__)
    log.disabled = True
    mail = Mail(flask_app)
    yield flask_app

@pytest.fixture
def client(app):
    return app.test_client()

"""
Reusable functions For:
1. Verifying an account
2. Signing up
3. Logging in
"""
def verify(client, id):
    return client.get('/verify', query_string=dict(id=id), follow_redirects=True)

def signup(client, email, password, confirm_password, terms, privacy):
    return client.post('/signup', data=dict(
        email=email,
        password=password,
        confirm_password=confirm_password,
        terms=terms,
        privacy=privacy
    ), follow_redirects=True)

def login(client, email, password):
    return client.post('/login', data=dict(
        email=email,
        password=password
    ), follow_redirects=True)

def change_pwd(client, old_password, new_password, confirm_password):
    return client.post('/account', data=dict(
        old_password=old_password,
        new_password=new_password,
        confirm_password=confirm_password
    ), follow_redirects=True)

def request_reset(client, email):
    return client.post('/forgot', data=dict(
        email=email
    ), follow_redirects=True)

def reset_pwd(client, id, token, password, confirm_password):
    return client.post('/reset', data=dict(
        user_id=id,
        token=token,
        new_password=password,
        confirm_password=confirm_password
    ), follow_redirects=True)

"""
Test Index Variations:
1. Not Logged In (redirect to login page)
2. Logged In (redirect to groups page)
"""
def test_index(app, client):
    res1 = client.get('/', follow_redirects=True)
    assert res1.status_code == 200
    assert b"Please login to use this website." in res1.data

"""
Test Signup Variations: 
1. Invalid signup (passwords don't match)
2. Invalid signup (terms not accepted)
3. Invalid signup (privacy not accepted)
4. Valid signup
5. Invalid signup (email already exists)
6. Invalid signup (email is invalid)
7. Invalid signup (password is invalid)
8. Invalid signup (email is empty)
9. Invalid signup (password is empty)
10. Invalid signup (terms is empty)
11. Invalid signup (privacy is empty)
"""
def test_signup(app, client):    
    res1 = signup(client, 'smartnotes_uol@protonmail.com', 'Password1!', 'Password2!', True, True)
    assert res1.status_code == 200
    assert b'Passwords do not match' in res1.data
    with app.app_context():
        user = models.User.query.filter_by(email="smartnotes_uol@protonmail.com").all()
    assert len(user) is 0

    res2 = signup(client, 'smartnotes_uol@protonmail.com', 'Password1!', 'Password1!', '', True)
    assert res2.status_code == 200
    assert b'Oops an error has occurred' in res2.data
    with app.app_context():
        user = models.User.query.filter_by(email="smartnotes_uol@protonmail.com").all()
    assert len(user) is 0

    res3 = signup(client, 'smartnotes_uol@protonmail.com', 'Password1!', 'Password1!', True, '')
    assert res3.status_code == 200
    assert b'Oops an error has occurred' in res3.data
    with app.app_context():
        user = models.User.query.filter_by(email="smartnotes_uol@protonmail.com").all()
    assert len(user) is 0

    res4 = signup(client, 'smartnotes_uol@protonmail.com', 'Password1!', 'Password1!', True, True)
    assert res4.status_code == 200
    assert b'Account created successfully' in res4.data
    assert b'Verification email sent' in res4.data
    with app.app_context():
        user = models.User.query.filter_by(email="smartnotes_uol@protonmail.com").all()
    assert user is not None
    assert len(user) == 1
    assert user[0].activated == False

    res5 = signup(client, 'smartnotes_uol@protonmail.com', 'Password1!', 'Password1!', True, True)
    assert res5.status_code == 200
    assert b'Email already in use' in res5.data
    with app.app_context():
        user = models.User.query.filter_by(email="smartnotes_uol@protonmail.com").all()
    assert len(user) is 1

    res6 = signup(client, 'smartnotes_uolprotonmail.com', 'Password1!', 'Password1!', True, True)
    assert res6.status_code == 200
    assert b'Invalid email' in res6.data
    with app.app_context():
        user = models.User.query.filter_by(email="smartnotes_uolprotonmail.com").all()
    assert len(user) is 0

    res7 = signup(client, 'charrison16082002@gmail.com', 'password', 'password', True, True)
    assert res7.status_code == 200
    assert b'Password must have at least 8 characters, 1 uppercase, 1 lowercase, 1 number, 1 special character' in res7.data
    with app.app_context():
        user = models.User.query.filter_by(email="charrison16082002@gmail.com").all()
    assert len(user) is 0

    res8 = client.post('/signup', data=dict(
            password='Password1!',
            confirm_password='Password1!',
            terms=True,
            privacy=True
        ), follow_redirects=True)
    assert res8.status_code == 200
    assert b'Oops an error has occurred.' in res8.data
    with app.app_context():
        user = models.User.query.filter_by(email="").all()
    assert len(user) is 0

    res9 = client.post('/signup', data=dict(
            email="charrison16082002@gmail.com",
            confirm_password='Password1!',
            terms=True,
            privacy=True
        ), follow_redirects=True)
    assert res9.status_code == 200
    assert b'Oops an error has occurred.' in res9.data
    with app.app_context():
        user = models.User.query.filter_by(email="charrison16082002@gmail.com").all()
    assert len(user) is 0

    # TearDown: Delete any changes made
    with app.app_context():
        users = models.User.query.all()
        for user in users:
            if user.email in [
                "smartnotes_uol@protonmail.com",
                "charrison16082002@gmail.com"
            ]:
                db.session.delete(user)
        db.session.commit()

"""
Test Verify Variations: 
1. Invalid verify (no id)
2. Valid verify
3. Invalid verify (already verified)
4. Invalid verify (invalid id)
"""
def test_verify(app, client):
    res1 = client.get('/verify', follow_redirects=True)
    assert res1.status_code == 200
    assert b'Cannot verify email. User not found' in res1.data

    signup(client, 'smartnotes_uol@protonmail.com', 'Password1!', 'Password1!', True, True)
    with app.app_context():
        user = models.User.query.filter_by(email="smartnotes_uol@protonmail.com").first()

    res2 = verify(client, user.id)
    with app.app_context():
        user = models.User.query.filter_by(email="smartnotes_uol@protonmail.com").first()
    assert res2.status_code == 200
    print(user.id)
    print("\n")
    print(res2.data)
    assert b'Email verified successfully' in res2.data
    assert user.activated == True

    res3 = verify(client, user.id)
    assert res3.status_code == 200
    assert b'User already activated' in res3.data

    res4 = verify(client, -1)
    assert res4.status_code == 200
    assert b'Cannot verify email. User not found' in res4.data

    # TearDown: Delete any changes made
    with app.app_context():
        db.session.delete(user)
        db.session.commit()

"""
Test Login Variations:
1. Invalid login (no email)
2. Invalid login (no password)
3. Invalid login (invalid email)
4. Invalid login (unverified email)
5. Invalid login (invalid password)
6. Invalid login (locked account)
7. Valid login 
"""
def test_login(app, client):
    signup(client, 'smartnotes_uol@protonmail.com', 'Password1!', 'Password1!', True, True)

    res1 = client.post('/login', data=dict(
        password='Password1!'
    ), follow_redirects=True)
    assert res1.status_code == 200
    assert b'Oops an error has occurred' in res1.data

    res2 = client.post('/login', data=dict(
        password='Password1!'
    ), follow_redirects=True)
    assert res1.status_code == 200
    assert b'Oops an error has occurred' in res1.data

    res3 = login(client, 'somebody@email.com', 'Password1!')
    assert res3.status_code == 200
    assert b'Email or Password Incorrect' in res3.data

    res4 = login(client, 'smartnotes_uol@protonmail.com', 'Password1!')
    assert res4.status_code == 200
    assert b'Please verify your email' in res4.data

    with app.app_context():
        user = models.User.query.filter_by(email="smartnotes_uol@protonmail.com").first()
    verify(client, user.id)

    res5 = login(client, 'smartnotes_uol@protonmail.com', 'Password2!')
    assert res5.status_code == 200
    assert b'Email or Password Incorrect' in res5.data

    login(client, 'smartnotes_uol@protonmail.com', 'Password2!')
    login(client, 'smartnotes_uol@protonmail.com', 'Password2!')
    login(client, 'smartnotes_uol@protonmail.com', 'Password2!')
    login(client, 'smartnotes_uol@protonmail.com', 'Password2!')

    res6 = login(client, 'smartnotes_uol@protonmail.com', 'Password1!')
    assert res6.status_code == 200
    assert b'Account is locked' in res6.data

    # Unlock account by changing expire time
    with app.app_context():
        user = models.User.query.filter_by(email="smartnotes_uol@protonmail.com").first()
        user.expire = datetime.now() - timedelta(minutes=20)
        db.session.commit()
    
    res7 = login(client, 'smartnotes_uol@protonmail.com', 'Password1!')
    assert res7.status_code == 200
    assert b'Login Successful' in res7.data

    # TearDown: Delete any changes made
    with app.app_context():
        db.session.delete(user)
        db.session.commit()

"""
Test Logout Variations:
1. Valid logout
"""
def test_logout(app, client):
    signup(client, 'smartnotes_uol@protonmail.com', 'Password1!', 'Password1!', True, True)
    with app.app_context():
        user = models.User.query.filter_by(email="smartnotes_uol@protonmail.com").first()
    verify(client, user.id)
    res = login(client, 'smartnotes_uol@protonmail.com', 'Password1!')
    assert res.status_code == 200
    assert b'Login Successful' in res.data
    res = client.get('/logout', follow_redirects=True)
    assert res.status_code == 200
    assert b'Logout Successful' in res.data

    # TearDown: Delete any changes made
    with app.app_context():
        db.session.delete(user)
        db.session.commit()

"""
Test Change Password Variations:
1. Invalid change password (no old password)
2. Invalid change password (no new password)
3. Invalid change password (no confirm password)
4. Invalid change password (invalid old password)
5. Invalid change password (new password and confirm password do not match)
6. Invalid change password (new password is invalid i.e. not 8+ chars, 1+ uppercase etc)
7. Valid change password (Ensure login works with new password)
"""
def test_change_pwd(app, client):
    signup(client, 'smartnotes_uol@protonmail.com', 'Password1!', 'Password1!', True, True)
    with app.app_context():
        user = models.User.query.filter_by(email="smartnotes_uol@protonmail.com").first()
    verify(client, user.id)
    login(client, 'smartnotes_uol@protonmail.com', 'Password1!')

    res1 = change_pwd(client, '', 'Password2!', 'Password2!')
    assert res1.status_code == 200
    print(res1.data)
    assert b'Invalid Request Detected' in res1.data

    res2 = change_pwd(client, 'Password1!', '', 'Password2!')
    assert res2.status_code == 200
    assert b'Invalid Request Detected' in res2.data

    res3 = change_pwd(client, 'Password1!', 'Password2!', '')
    assert res3.status_code == 200
    assert b'Invalid Request Detected' in res3.data

    res4 = change_pwd(client, 'Password2!', 'Password3!', 'Password3!')
    assert res4.status_code == 200
    assert b'Invalid Password' in res4.data
    
    res5 = change_pwd(client, 'Password1!', 'Password2!', 'Password3!')
    assert res5.status_code == 200
    assert b'Passwords do not match' in res5.data

    res6 = change_pwd(client, 'Password1!', 'pass', 'pass')
    assert res6.status_code == 200
    assert b'Password must have at least 8 characters, 1 uppercase, 1 lowercase, 1 number, 1 special character' in res6.data

    res7 = change_pwd(client, 'Password1!', 'Password2!', 'Password2!')
    assert res7.status_code == 200
    assert b'Password Changed' in res7.data
    client.get('/logout', follow_redirects=True)
    res8 = login(client, 'smartnotes_uol@protonmail.com', 'Password2!')
    assert res8.status_code == 200
    assert b'Login Successful' in res8.data

    # TearDown: Delete any changes made
    with app.app_context():
        db.session.delete(user)
        db.session.commit()

"""
Test Forgot Password Variations:
1. Invalid forgot password (no email)
2. Invalid forgot password (invalid email)
3. Valid forgot password
"""
def test_forgot_password(app, client):
    signup(client, 'smartnotes_uol@protonmail.com', 'Password1!', 'Password1!', True, True)
    with app.app_context():
        user = models.User.query.filter_by(email="smartnotes_uol@protonmail.com").first()
    verify(client, user.id)

    res1 = request_reset(client, '')
    assert res1.status_code == 200
    assert b'Cannot reset password. Invalid form' in res1.data

    res2 = request_reset(client, 'smartnotes_uol@proton.me')
    assert res2.status_code == 200
    assert b'Cannot reset password. User not found' in res2.data

    with app.app_context():
        token = models.PassToken.query.filter_by(user=user.id).first()
    assert token is None
    res3 = request_reset(client, 'smartnotes_uol@protonmail.com')
    assert res3.status_code == 200
    with app.app_context():
        token = models.PassToken.query.filter_by(user=user.id).first()
    assert token is not None

    # TearDown: Delete any changes made
    with app.app_context():
        db.session.delete(user)
        db.session.delete(token)
        db.session.commit()

"""
Test Reset Password Variations:
1. Invalid reset password (no id)
2. Invalid reset password (no token)
3. Invalid reset password (no new password)
4. Invalid reset password (no confirm password)
5. Invalid reset password (invalid id)
6. Invalid reset password (invalid token)
7. Invalid reset password (new password and confirm password do not match)
8. Invalid reset password (new password is invalid i.e. not 8+ chars, 1+ uppercase etc)
9. Valid reset password (Ensure login works with new password)
10. Invalid reset password (token expired)
"""
def test_reset_password(app, client):
    signup(client, 'smartnotes_uol@protonmail.com', 'Password1!', 'Password1!', True, True)
    with app.app_context():
        user = models.User.query.filter_by(email="smartnotes_uol@protonmail.com").first()
    verify(client, user.id)
    with app.app_context():
        token = models.PassToken.query.filter_by(user=user.id).first()
    assert token is None
    request_reset(client, 'smartnotes_uol@protonmail.com')
    with app.app_context():
        token = models.PassToken.query.filter_by(user=user.id).first()
    assert token is not None

    res1 = reset_pwd(client, '', token.token, 'Password2!', 'Password2!')
    assert res1.status_code == 200
    assert b'Cannot reset password. Invalid form' in res1.data

    res2 = reset_pwd(client, user.id, '', 'Password2!', 'Password2!')
    assert res2.status_code == 200
    assert b'Cannot reset password. Invalid form' in res2.data

    res3 = reset_pwd(client, user.id, token.token, '', 'Password2!')
    assert res3.status_code == 200
    assert b'Cannot reset password. Invalid form' in res3.data

    res4 = reset_pwd(client, user.id, token.token, 'Password2!', '')
    assert res4.status_code == 200
    assert b'Cannot reset password. Invalid form' in res4.data

    res5 = reset_pwd(client, 20, token.token, 'Password2!', 'Password2!')
    assert res5.status_code == 200
    assert b'Cannot reset password. User not found' in res5.data

    res6 = reset_pwd(client, user.id, '0', 'Password2!', 'Password2!')
    assert res6.status_code == 200
    assert b'Cannot reset password. Token not found' in res6.data

    res7 = reset_pwd(client, user.id, token.token, 'Password2!', 'Password3!')
    assert res7.status_code == 200
    assert b'Cannot reset password. Passwords do not match' in res7.data

    res8 = reset_pwd(client, user.id, token.token, 'pass', 'pass')
    assert res8.status_code == 200
    assert b'Cannot reset password. Password does not meet requirements' in res8.data

    res9 = reset_pwd(client, user.id, token.token, 'Password1!0', 'Password1!0')
    assert res9.status_code == 200
    assert b'Password reset successful' in res9.data
    res9a = login(client, 'smartnotes_uol@protonmail.com', 'Password1!0')
    assert res9a.status_code == 200
    assert b'Login Successful' in res9a.data

    client.get('/logout')
    with app.app_context():
        token2 = models.PassToken(user=user.id, token='0', expire=datetime.now() - timedelta(minutes=30))
        db.session.add(token2)
        db.session.commit()
    res10 = reset_pwd(client, user.id, '0', 'Password1!1', 'Password1!1')
    assert res10.status_code == 200
    assert b'Cannot reset password. Token expired' in res10.data

    # TearDown: Delete any changes made
    with app.app_context():
        db.session.delete(user)
        db.session.delete(token2) # token1 is deleted when password changed in res9
        db.session.commit()