import os

basedir = os.path.abspath(os.path.dirname(__file__))
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