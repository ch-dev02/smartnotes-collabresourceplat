from app import db, login_manager
from flask_login import UserMixin

@login_manager.user_loader
def load_user(id):
    return User.query.get(int(id))

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(256), index=True, unique=True)
    password_hash = db.Column(db.String(256))
    attempts = db.Column(db.Integer, default=5)
    locked = db.Column(db.Boolean, default=False)
    expire = db.Column(db.DateTime, default=None)
    activated = db.Column(db.Boolean, default=False)

class PassToken(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user = db.Column(db.Integer, db.ForeignKey('user.id'))
    token = db.Column(db.String(256), unique=True)
    expire = db.Column(db.DateTime)

class Group(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(256))
    code = db.Column(db.String(256), unique=True)
    owner = db.Column(db.Integer, db.ForeignKey('user.id'))

class Member(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user = db.Column(db.Integer, db.ForeignKey('user.id'))
    group = db.Column(db.Integer, db.ForeignKey('group.id'))

class Folder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(256))
    group = db.Column(db.Integer, db.ForeignKey('group.id'))

class Resource(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(256))
    creator = db.Column(db.Integer, db.ForeignKey('user.id'))
    folder = db.Column(db.Integer, db.ForeignKey('folder.id'))
    type = db.Column(db.String(256))
    data = db.Column(db.Text)

class Keywords(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    resource = db.Column(db.Integer, db.ForeignKey('resource.id'))
    json = db.Column(db.Text)

class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    creator = db.Column(db.Integer, db.ForeignKey('user.id'))
    resource = db.Column(db.Integer, db.ForeignKey('resource.id'))
    comment = db.Column(db.String(256))
    rating = db.Column(db.Integer)

class Queue(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    resource = db.Column(db.Integer, db.ForeignKey('resource.id'))

# Available Resource Types:
#   - 'material' (PDF, upload on site, data=filename)
#   - 'transcript' (TXT, upload on site, data=filename)
#   - 'notes' (MD, input on site, no upload, data=content)
#   - 'url' (URL, input on site, no upload, data=url)