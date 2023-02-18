from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_admin import Admin
from flask_mail import Mail
import logging

logging.basicConfig(filename='log.log', level=logging.INFO, format='%(asctime)s %(levelname)s : %(message)s')

app = Flask(__name__)
app.config.from_object('config')

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please login to use this website.'
login_manager.login_message_category = 'primary'

mail = Mail(app)

db = SQLAlchemy(app)
migrate = Migrate(app, db)

admin = Admin(app, name='Admin', template_mode='bootstrap3')

from app.views import auth, grp
from app import models