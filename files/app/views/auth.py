from app import app, db, models, admin
from flask_admin.contrib.sqla import ModelView
from flask import render_template, request, flash, redirect, url_for, Markup
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