import os

basedir = os.path.abspath(os.path.dirname(__file__))
if os.getenv("TESTING") is not None:
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'test.db')
else:
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'app.db')
SQLALCHEMY_TRACK_MODIFICATIONS = True    

MAIL_SERVER='smtp.gmail.com'
MAIL_PORT = 465
MAIL_USERNAME = 'smartnotesuol@gmail.com'
MAIL_PASSWORD = 'pwiighbtketheqnd'
MAIL_USE_TLS = False
MAIL_USE_SSL = True

WTF_CSRF_ENABLED = True
SECRET_KEY = 'b4StrEde2N*WJx'

MAX_CONTENT_LENGTH = 16 * 1000 * 1000
UPLOAD_FOLDER = 'app/static/uploads'

EXECUTOR_MAX_WORKERS = 1
EXECUTOR_TYPE = 'thread'
EXECUTOR_PROPAGATE_EXCEPTIONS = True