from app import app, db, models
from flask import render_template, request, flash, redirect, url_for, send_file
from flask_login import current_user, login_required
from ..forms import *
import logging
import html
import json
import secrets
import validators
from werkzeug.utils import secure_filename
import os

logger = logging.getLogger(__name__)

"""
Home Page
User must be logged in
GET request only
 - get all groups user is a member of
 - get all groups user owns
 - merge groups and sort by title
 - render index.html
"""
@app.route('/', methods=['GET'])
@login_required
def index():
    groups = models.Group.query.filter_by(owner=current_user.id).all()
    member_groups = models.Member.query.filter_by(user=current_user.id).all()
    for group in member_groups:
        group = models.Group.query.filter_by(id=group.group).first()
        groups.append(group)
    groups.sort(key=lambda x: x.title)
    logger.info('User ' + current_user.email + ' accessed home page')
    return render_template('index.html', groups=groups)

"""
Create Group Page
User must be logged in
GET request
 - render create-group.html
POST request and form is valid
 - generate unique code
 - create group
 - redirect to home page
POST request and form is invalid
 - render create-group.html with error message
"""
@app.route('/create-group', methods=['GET', 'POST'])
@login_required
def create_group():
    form = CreateGroupForm()
    if request.method == 'GET':
        logger.info('User ' + current_user.email + ' accessed create group page')
        return render_template('create-group.html', form=form)
    elif form.validate_on_submit():
        code = secrets.token_urlsafe(8)
        while models.Group.query.filter_by(code=code).first():
            code = secrets.token_urlsafe(8)
        title = html.escape(form.title.data)
        group = models.Group(title=title, code=code, owner=current_user.id)
        db.session.add(group)
        db.session.commit()
        logger.info('User ' + current_user.email + ' created group ' + title + ": " + code)
        flash('Group created successfully.\nShare the code: `'+code+'` to invite people to the group.', 'success')
        return redirect(url_for('index'))
    else:
        logger.error('User ' + current_user.email + ' sent invalid post request to create group page')
        flash('Error creating group', 'danger')
        return render_template('create-group.html', form=form)

"""
Join Group Page
User must be logged in
GET request
 - render join-group.html
POST request and form is valid
 - get group from code
 - add user to group
 - redirect to home page
POST request and form is invalid
 - render join-group.html with error message
"""
@app.route('/join-group', methods=['GET', 'POST'])
@login_required
def join_group():
    form = JoinGroupForm()
    if request.method == 'GET':
        logger.info('User ' + current_user.email + ' accessed join group page')
        return render_template('join-group.html', form=form)
    elif form.validate_on_submit():
        code = html.escape(form.code.data)
        group = models.Group.query.filter_by(code=code).first()
        if group:
            member = models.Member(user=current_user.id, group=group.id)
            db.session.add(member)
            db.session.commit()
            logger.info('User ' + current_user.email + ' joined group ' + group.title + ": " + code)
            flash('Joined group successfully.', 'success')
            return redirect(url_for('index'))
        else:
            logger.error('User ' + current_user.email + ' sent wanted to join invalid group ' + code)
            flash('Error joining group, group doesn\'t exist', 'danger')
            return render_template('join-group.html', form=form)
    else:
        logger.error('User ' + current_user.email + ' sent invalid post request to join group page')
        flash('Error joining group, group doesn\'t exist', 'danger')
        return render_template('join-group.html', form=form)

"""
Group Page
User must be logged in
Check if group exists
 - if not warn and log then return to home page
Otherwise
 - Get All folders
 - Get the leave/delete form and prefill group_id
 - Check user is member or group owner
   - If not warn and log then return to home page
 - If user owns group
   - Get the create folder form and prefill group_id
 - Render group.html
"""
@app.route('/group/<id>', methods=['GET'])
@login_required
def group(id):
    group = models.Group.query.filter_by(id=id).first()
    form = DelLeaveGroupForm()
    form.group_id.data = id
    if not group:
        flash('Group doesn\'t exist', 'danger')
        logger.info('User ' + current_user.email + ' tried to access invalid group: ' + id)
        return redirect(url_for('index'))

    member = models.Member.query.filter_by(user=current_user.id, group=group.id).first()
    if not member and group.owner != current_user.id:
        flash('You don\'t have permission to access this group', 'danger')
        logger.warn('User ' + current_user.email + ' tried to access group: ' + str(group.id) + ' without permission')
        return redirect(url_for('index'))
    
    folders = models.Folder.query.filter_by(group=group.id).all()
    logger.info('User ' + current_user.email + ' accessed group: ' + str(group.id))
    if group.owner == current_user.id:
        form2 = CreateFolderForm()
        form2.group_id.data = id
        return render_template('group.html', group=group, folders=folders, form=form,form_create_folder=form2)
    return render_template('group.html', group=group, folders=folders, form=form)

"""
Create Folder Route
User must be logged in
Uses Create form created in /group/<id> route
If form doesn't validate
 - warn and log then return to group page
Otherwise
 - Check if group exists
   - if not warn and log then return to home page
 - Check if user owns group
   - if not warn and log then return to group page
 - Create folder
 - Redirect to group page
"""
@app.route('/folder/create', methods=['POST'])
@login_required
def create_folder():
    form = CreateFolderForm()
    if form.validate_on_submit():
        title = html.escape(form.title.data)
        group_id = form.group_id.data
        group = models.Group.query.filter_by(id=group_id).first()
        if not group:
            flash('Group doesn\'t exist', 'danger')
            logger.info('User ' + current_user.email + ' tried to create folder in invalid group: ' + str(group_id))
            return redirect(url_for('index'))

        if group.owner != current_user.id:
            flash('You don\'t have permission to create folders in this group', 'danger')
            logger.warning('User ' + current_user.email + ' tried to create folder in group: ' + str(group_id) + ' without permission')
            return redirect(url_for('group', id=group_id))

        folder = models.Folder(title=title, group=group_id)
        db.session.add(folder)
        db.session.commit()
        logger.info('User ' + current_user.email + ' created folder ' + title + ' in group: ' + str(group_id))
        flash('Folder created successfully.', 'success')
        return redirect(url_for('group', id=group_id))
    else:
        flash('Error creating folder', 'danger')
        logger.info('User ' + current_user.email + ' sent invalid request to create folder')
        return redirect(url_for('index'))

"""
Folder Page
User must be logged in
Check if folder exists
 - if not warn and log then return to home page
Check if parent group exists
 - if not warn and log then return to home page
Check if user is a member of parent group or the owner
 - if not warn and log then return to home page
"""
@app.route('/folder/<id>', methods=['GET'])
@login_required
def folder(id):
    form = DelFolderForm()
    form.folder_id.data = id
    folder = models.Folder.query.filter_by(id=id).first()
    if not folder:
        flash('Folder doesn\'t exist', 'danger')
        logger.info('User ' + current_user.email + ' tried to access invalid folder: ' + str(id))
        return redirect(url_for('index'))
    group = models.Group.query.filter_by(id=folder.group).first()
    if not group:
        flash('Folder\'s parent group doesn\'t exist', 'danger')
        logger.info('User ' + current_user.email + ' tried to access folder in invalid group: ' + str(folder.group))
        return redirect(url_for('index'))
    member = models.Member.query.filter_by(user=current_user.id, group=group.id).first()
    if group.owner != current_user.id and not member:
        flash('You don\'t have permission to access this folder', 'danger')
        logger.warning('User ' + current_user.email + ' tried to access folder: ' + str(id) + ' without permission')
        return redirect(url_for('index'))
    logger.info('User ' + current_user.email + ' accessed folder: ' + str(folder.id))
    return render_template('folder.html', folder=folder, owner=group.owner, form=form, group_title=group.title, group_id=group.id)

"""
Delete folder route
User must be logged in
Post Request Only
If form is valid:
  Check if folder exists
  Check if parent group exists
  Check if user has permission to delete (group owner)
  Delete all resources in folder
  Delete all reviews for resources in folder
  Delete all files for resources in folder
  Delete folder
  Log action
  Redirect to group page
Else:
  Log invalid request
  Flash error
  Redirect to index
"""
@app.route('/folder/delete', methods=['POST'])
@login_required
def delete_folder():
    form = DelFolderForm()
    if form.validate_on_submit():
        folder = models.Folder.query.filter_by(id=form.folder_id.data).first()
        if not folder:
            logger.info('User ' + current_user.email + ' sent invalid request to delete folder ' + str(form.folder_id.data))
            flash("Invalid request", "danger")
            return redirect(url_for('index'))
        group = models.Group.query.filter_by(id=folder.group).first()
        if not group:
            logger.info('User ' + current_user.email + ' sent invalid request to delete folder ' + str(form.folder_id.data) + " with missing group")
            flash("Invalid request", "danger")
            return redirect(url_for('index'))
        if group.owner != current_user.id:
            logger.warning('User ' + current_user.email + ' tried to delete folder without permission')
            flash("You do not have permission to delete this folder", "danger")
            return redirect(url_for('index'))
        # Do some stuff to delete resources once they are implemented
        db.session.delete(folder)
        db.session.commit()
        logger.info('User ' + current_user.email + ' deleted folder ' + str(form.folder_id.data))
        flash("Folder deleted", "success")
        return redirect(url_for('group', id=group.id))
    else:
        logger.info('User ' + current_user.email + ' sent invalid request to delete folder ' + str(form.folder_id.data))
        flash("Invalid request", "danger")
        return redirect(url_for('index'))

"""
Delete group route
User must be logged in
Post Request Only
If form is valid:
  Check if group exists
  Check if user is owner of group
  Delete all members of group
  Delete all folders in group
  Delete all resources in folders in group
  Delete all reviews of resources in folders in group
  Delete all files of resources in folders in group
  Delete group
  Log action
  Redirect to index
Else:
  Log invalid request
  Flash error
  Redirect to index
"""
@app.route('/group/delete', methods=['POST'])
@login_required
def delete_group():
    form = DelLeaveGroupForm()
    if form.validate_on_submit():
        id = int(form.group_id.data)
        group = models.Group.query.filter_by(id=id).first()
        if not group:
            logger.info('User ' + current_user.email + ' sent invalid request to leave group ' + str(id))
            flash("Invalid request, this group doesn't exist", "danger")
            return redirect(url_for('index'))
        if group.owner != current_user.id:
            logger.info('User ' + current_user.email + ' sent invalid request to leave group ' + str(id))
            flash("You cannot delete a group you do not own.", "danger")
            return redirect(url_for('index'))
        members = models.Member.query.filter_by(group=id).all()
        for member in members:
            db.session.delete(member)
        folders = models.Folder.query.filter_by(group=id).all()
        for folder in folders:
            # Do some stuff to delete resources once they are implemented
            db.session.delete(folder)
        db.session.delete(group)
        db.session.commit()
        logger.info('User ' + current_user.email + ' deleted group ' + str(id))
        flash("You have deleted the group", "success")
        return redirect(url_for('index'))
    else:
        logger.info('User ' + current_user.email + ' sent invalid request to delete group ' + str(form.group_id.data))
        flash("Invalid request", "danger")
        return redirect(url_for('index'))


"""
Leave group route
User must be logged in
POST request only
Check form is valid
  Get group and check if valid
  Check user is a member of the group and is not the owner
  Delete membership
  Delete all resources created by user in group and their reviews
  Delete all reviews by user in group
  Commit changes
  Redirect to index
"""
@app.route('/group/leave', methods=['POST'])
@login_required
def leave_group():
    form = DelLeaveGroupForm()
    if form.validate_on_submit():
        id = int(form.group_id.data)
        group = models.Group.query.filter_by(id=id).first()
        if not group:
            logger.info('User ' + current_user.email + ' sent invalid request to leave group ' + str(id))
            flash("Invalid request, this group doesn't exist", "danger")
            return redirect(url_for('index'))
        if group.owner == current_user.id:
            logger.info('User ' + current_user.email + ' sent invalid request to leave group ' + str(id))
            flash("You cannot leave a group you own, you may delete it instead.", "danger")
            return redirect(url_for('index'))
        member = models.Member.query.filter_by(user=current_user.id, group=id).first()
        if not member:
            logger.info('User ' + current_user.email + ' sent invalid request to leave group ' + str(id))
            flash("Invalid request, you are not a member of this group", "danger")
            return redirect(url_for('index'))
        db.session.delete(member)
        # Do some stuff to delete resources once they are implemented    
        db.session.commit()
        logger.info('User ' + current_user.email + ' left group ' + str(id))
        flash("You have left the group", "success")
        return redirect(url_for('index'))
    else:
        logger.info('User ' + current_user.email + ' sent invalid request to leave group ' + str(form.group_id.data))
        flash("Invalid request", "danger")
        return redirect(url_for('index'))