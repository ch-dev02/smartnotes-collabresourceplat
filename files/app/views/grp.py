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
import math
from ..scripts import *

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
Add Lecture Material
User must be logged in
Get folder id as int and Check if folder exists
 - if not warn and log then return to home page
Check if parent group exists
 - if not warn and log then return to home page
Check if user is a member of parent group or the owner
 - if not warn and log then return to home page
GET request
 - Render upload_material.html
POST request and form validates
 - Check if title is valid and not already in folder
   - if not warn and log then return to folder page
 - Check if file is valid
   - if not warn and log then return to folder page
 - If file with same name exists in folder
   - Generate random string to prepend to filename
 - Create Resource
 - Redirect to folder page
POST request and form doesn't validate
 - warn user, log and redirect to folder page
"""
@app.route('/upload_material', methods=['GET', 'POST'])
@login_required
def upload_material():
    form = UploadFileForm()
    if request.args.get('folder') is None or not request.args.get('folder').isdigit():
        flash('Invalid request', 'danger')
        logger.info('User ' + current_user.email + ' sent invalid request to add lecture material')
        return redirect(url_for('index'))
    id = int(request.args.get('folder'))
    folder = models.Folder.query.filter_by(id=id).first()
    if not folder:
        flash('Folder doesn\'t exist', 'danger')
        logger.info('User ' + current_user.email + ' tried to add lecture material to invalid folder: ' + str(id))
        return redirect(url_for('index'))
    group = models.Group.query.filter_by(id=folder.group).first()
    if not group:
        flash('Folder\'s parent group doesn\'t exist', 'danger')
        logger.info('User ' + current_user.email + ' tried to add lecture material to folder in invalid group: ' + str(folder.group))
        return redirect(url_for('index'))
    member = models.Member.query.filter_by(user=current_user.id, group=group.id).first()
    if group.owner != current_user.id and not member:
        flash('You don\'t have permission to add to this folder', 'danger')
        logger.warning('User ' + current_user.email + ' tried to add lecture material to folder: ' + str(id) + ' without permission')
        return redirect(url_for('index'))
    if request.method == 'GET':
        logger.info('User ' + current_user.email + ' accessed upload lecture material page for folder: ' + str(id))
        return render_template('upload_file.html', form=form, title='Upload Lecture Material', action_url=url_for('upload_material', folder=id), form_name="upload_material", accepts=".pdf")
    elif form.validate_on_submit():
        title = html.escape(form.title.data.strip())
        existing = models.Resource.query.filter_by(title=title, folder=id).first()
        if title == '':
            flash('Title cannot be empty', 'danger')
            logger.info('User ' + current_user.email + ' sent invalid request to add lecture material')
            return redirect(url_for('upload_material', folder=id))
        if existing:
            flash('Resource with that title already exists', 'danger')
            logger.info('User ' + current_user.email + ' tried to add duplicate resource title to folder: ' + str(id))
            return redirect(url_for('upload_material', folder=id))
        if 'file' not in request.files:
            flash('No file detected', 'danger')
            logger.info('User ' + current_user.email + ' sent invalid request to add lecture material')
            return redirect(url_for('upload_material', folder=id))
        file = request.files['file']
        if file.filename == '':
            flash('No file detected', 'danger')
            logger.info('User ' + current_user.email + ' sent invalid request to add lecture material')
            return redirect(url_for('upload_material', folder=id))
        if file and allowed_file(file.filename, ['pdf']):
            upfolder = "g" + str(group.id) + "f" + str(folder.id)
            if not os.path.isdir(os.path.join(app.config['UPLOAD_FOLDER'], upfolder)):
                os.mkdir(os.path.join(app.config['UPLOAD_FOLDER'], upfolder))
            filename = secure_filename(file.filename)
            rnd = ''
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], upfolder, filename)
            while os.path.isfile(filepath):
                rnd = secrets.token_urlsafe(8)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], upfolder, rnd+"_"+filename)
            file.save(filepath)
            # Create resource
            resource = models.Resource(data=filepath, title=title, folder=id, creator=current_user.id, type="material")
            db.session.add(resource)
            db.session.commit()
            flash("File uploaded", "success")
            logger.info('User ' + current_user.email + ' uploaded lecture material ' + str(resource.id) + ' to folder ' + str(id))
            return redirect(url_for('folder', id=id))
        flash('Invalid file type', 'danger')
        logger.info('User ' + current_user.email + ' tried to upload invalid file type to folder: ' + str(id))
        return redirect(url_for('upload_material', folder=id))
    else:
        flash('Error uploading file', 'danger')
        logger.info('User ' + current_user.email + ' sent invalid request to upload lecture material to folder: ' + str(id))
        return redirect(url_for('folder', id=id))

"""
Add Lecture Transcript
User must be logged in
Get folder id as int and Check if folder exists
 - if not warn and log then return to home page
Check if parent group exists
 - if not warn and log then return to home page
Check if user is a member of parent group or the owner
 - if not warn and log then return to home page
GET request
 - Render upload_transcript.html
POST request and form validates
 - Check if title is valid and not already in folder
   - if not warn and log then return to folder page
 - Check if file is valid
   - if not warn and log then return to folder page
 - If file with same name exists in folder
   - Generate random string to prepend to filename
 - Create Resource
 - Redirect to folder page
POST request and form doesn't validate
 - warn user, log and redirect to folder page
"""
@app.route('/upload_transcript', methods=['GET', 'POST'])
@login_required
def upload_transcript():
    form = UploadFileForm()
    if request.args.get('folder') is None or not request.args.get('folder').isdigit():
        flash('Invalid request', 'danger')
        logger.info('User ' + current_user.email + ' sent invalid request to add lecture transcript')
        return redirect(url_for('index'))
    id = int(request.args.get('folder'))
    folder = models.Folder.query.filter_by(id=id).first()
    if not folder:
        flash('Folder doesn\'t exist', 'danger')
        logger.info('User ' + current_user.email + ' tried to add lecture transcript to invalid folder: ' + str(id))
        return redirect(url_for('index'))
    group = models.Group.query.filter_by(id=folder.group).first()
    if not group:
        flash('Folder\'s parent group doesn\'t exist', 'danger')
        logger.info('User ' + current_user.email + ' tried to add lecture transcript to folder in invalid group: ' + str(folder.group))
        return redirect(url_for('index'))
    member = models.Member.query.filter_by(user=current_user.id, group=group.id).first()
    if group.owner != current_user.id and not member:
        flash('You don\'t have permission to add to this folder', 'danger')
        logger.warning('User ' + current_user.email + ' tried to add lecture transcript to folder: ' + str(id) + ' without permission')
        return redirect(url_for('index'))
    if request.method == 'GET':
        logger.info('User ' + current_user.email + ' accessed upload lecture transcript page for folder: ' + str(id))
        return render_template('upload_file.html', form=form, title='Upload Lecture Transcript', action_url=url_for('upload_transcript', folder=id), form_name="upload_transcript", accepts=".txt, .vtt")
    elif form.validate_on_submit():
        title = html.escape(form.title.data.strip())
        existing = models.Resource.query.filter_by(title=title, folder=id).first()
        if title == '':
            flash('Title cannot be empty', 'danger')
            logger.info('User ' + current_user.email + ' sent invalid request to add lecture transcript')
            return redirect(url_for('upload_transcript', folder=id))
        if existing:
            flash('Resource with that title already exists', 'danger')
            logger.info('User ' + current_user.email + ' tried to add duplicate resource title to folder: ' + str(id))
            return redirect(url_for('upload_transcript', folder=id))
        if 'file' not in request.files:
            flash('No file detected', 'danger')
            logger.info('User ' + current_user.email + ' sent invalid request to add lecture transcript')
            return redirect(url_for('upload_transcript', folder=id))
        file = request.files['file']
        if file.filename == '':
            flash('No file detected', 'danger')
            logger.info('User ' + current_user.email + ' sent invalid request to add lecture transcript')
            return redirect(url_for('upload_transcript', folder=id))
        if file and allowed_file(file.filename, ['vtt', 'txt']):
            upfolder = "g" + str(group.id) + "f" + str(folder.id)
            if not os.path.isdir(os.path.join(app.config['UPLOAD_FOLDER'], upfolder)):
                os.mkdir(os.path.join(app.config['UPLOAD_FOLDER'], upfolder))
            filename = secure_filename(file.filename)
            rnd = ''
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], upfolder, filename)
            while os.path.isfile(filepath):
                rnd = secrets.token_urlsafe(8)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], upfolder, rnd+"_"+filename)
            file.save(filepath)
            # Create resource
            resource = models.Resource(data=filepath, title=title, folder=id, creator=current_user.id, type="transcript")
            db.session.add(resource)
            db.session.commit()
            flash("File uploaded", "success")
            logger.info('User ' + current_user.email + ' uploaded lecture transcript ' + str(resource.id) + ' to folder ' + str(id))
            return redirect(url_for('folder', id=id))
        flash('Invalid file type', 'danger')
        logger.info('User ' + current_user.email + ' tried to upload invalid file type to folder: ' + str(id))
        return redirect(url_for('upload_transcript', folder=id))
    else:
        flash('Error uploading file', 'danger')
        logger.info('User ' + current_user.email + ' sent invalid request to upload lecture transcript to folder: ' + str(id))
        return redirect(url_for('folder', id=id))

"""
Add notes page
User must be logged in
Folder id must be specified and validates
Folder's parent group must exist
User must be a member of the group or the group's owner
If user is member, cannot have >1 set of notes in folder
GET Request:
  - Render add notes page
POST Request and form validates:
  - Validate title and notes are not empty
  - HTML Escape title and notes
  - Validate title is unique in folder
  - Create resource
  - Redirect to folder page
POST Request and form does not validate:
  - Log and alert user to error
  - Redirect to folder page
"""
@app.route("/add_notes", methods=['GET', 'POST'])
@login_required
def add_notes():
    if request.args.get('folder') is None or not request.args.get('folder').isdigit():
        flash('Invalid request', 'danger')
        logger.info('User ' + current_user.email + ' sent invalid request to add notes')
        return redirect(url_for('index'))
    id = int(request.args.get('folder'))
    folder = models.Folder.query.filter_by(id=id).first()
    if not folder:
        flash('Folder doesn\'t exist', 'danger')
        logger.info('User ' + current_user.email + ' tried to add notes to invalid folder: ' + str(id))
        return redirect(url_for('index'))
    group = models.Group.query.filter_by(id=folder.group).first()
    if not group:
        flash('Folder\'s parent group doesn\'t exist', 'danger')
        logger.info('User ' + current_user.email + ' tried to add notes to folder in invalid group: ' + str(folder.group))
        return redirect(url_for('index'))
    member = models.Member.query.filter_by(user=current_user.id, group=group.id).first()
    if group.owner != current_user.id and not member:
        flash('You don\'t have permission to add to this folder', 'danger')
        logger.warning('User ' + current_user.email + ' tried to add notes to folder: ' + str(id) + ' without permission')
        return redirect(url_for('index'))
    other_notes = models.Resource.query.filter_by(folder=id, type="notes", creator=current_user.id).all()
    if other_notes and group.owner != current_user.id:
        flash('You already have notes in this folder. Please locate previous notes and edit those.', 'danger')
        logger.info('User ' + current_user.email + ' tried to add >1 set of notes to folder: ' + str(id))
        return redirect(url_for('folder', id=id))
    form = NotesForm()
    if request.method == 'GET':
        logger.info('User ' + current_user.email + ' requested add notes page for folder: ' + str(id))
        return render_template('add_notes.html', folder=folder, form=form, owner=group.owner)
    elif form.validate_on_submit():
        title = form.title.data
        notes = form.notes.data
        if title.strip() == '' or notes.strip() == '':
            flash('Fields cannot be empty', 'danger')
            logger.info('User ' + current_user.email + ' sent invalid request to add notes to folder: ' + str(id))
            return redirect(url_for('add_notes', folder=id))
        title = html.escape(title)
        notes = html.escape(notes)
        existing = models.Resource.query.filter_by(folder=id, title=title).all()
        if existing:
            flash('Title already exists in folder', 'danger')
            logger.info('User ' + current_user.email + ' sent invalid request to add notes to folder: ' + str(id))
            return redirect(url_for('add_notes', folder=id))
        resource = models.Resource(data=notes, title=title, folder=id, creator=current_user.id, type="notes")
        db.session.add(resource)
        db.session.commit()
        flash("Notes added", "success")
        logger.info('User ' + current_user.email + ' added notes ' + str(resource.id) + ' to folder ' + str(id))
        return redirect(url_for('folder', id=id))
    else:
        flash('Error adding notes', 'danger')
        logger.info('User ' + current_user.email + ' sent invalid request to add notes to folder: ' + str(id))
        return redirect(url_for('folder', id=id))

"""
Edit notes page
User must be logged in
Notes id must be specified and validates
Notes must exist
Folder must exist
User must be a member of the group or the group's owner
If user is member, cannot have >1 set of notes in folder
GET Request:
    - Render edit notes page
POST Request and form validates:
    - Validate title and notes are not empty
    - HTML Escape title and notes
    - Validate title is unique in folder
    - Update resource
    - Redirect to folder page
POST Request and form does not validate:
    - Log and alert user to error
    - Redirect to folder page
"""
@app.route("/edit_notes", methods=['GET', 'POST'])
@login_required
def edit_notes():
    if request.args.get('id') is None or not request.args.get('id').isdigit():
        flash('Invalid request', 'danger')
        logger.info('User ' + current_user.email + ' sent invalid request to edit notes')
        return redirect(url_for('index'))
    id = int(request.args.get('id'))
    resource = models.Resource.query.filter_by(id=id).first()
    if not resource:
        flash('Notes don\'t exist', 'danger')
        logger.info('User ' + current_user.email + ' tried to edit invalid notes: ' + str(id))
        return redirect(url_for('index'))
    folder = models.Folder.query.filter_by(id=resource.folder).first()
    if not folder:
        flash('Notes\' parent folder doesn\'t exist', 'danger')
        logger.info('User ' + current_user.email + ' tried to edit notes in invalid folder: ' + str(resource.folder))
        return redirect(url_for('index'))
    group = models.Group.query.filter_by(id=folder.group).first()
    if not group:
        flash('Notes\' parent folder\'s parent group doesn\'t exist', 'danger')
        logger.info('User ' + current_user.email + ' tried to edit notes in folder in invalid group: ' + str(folder.group))
        return redirect(url_for('index'))
    member = models.Member.query.filter_by(user=current_user.id, group=group.id).first()
    if group.owner != current_user.id and not member:
        flash('You don\'t have permission to edit these notes', 'danger')
        logger.warning('User ' + current_user.email + ' tried to edit notes: ' + str(id) + ' without permission')
        return redirect(url_for('index'))
    if resource.creator != current_user.id:
        flash('You don\'t have permission to edit these notes', 'danger')
        logger.warning('User ' + current_user.email + ' tried to edit notes: ' + str(id) + ' without permission')
        return redirect(url_for('index'))
    form = NotesForm()
    if request.method == 'GET':
        form.title.data = resource.title
        form.notes.data = html.unescape(resource.data)
        logger.info('User ' + current_user.email + ' requested edit notes page for notes: ' + str(id))
        return render_template('edit_notes.html', folder=folder, form=form, owner=group.owner)
    elif form.validate_on_submit():
        title = form.title.data
        notes = form.notes.data
        if title.strip() == '' or notes.strip() == '':
            flash('Fields cannot be empty', 'danger')
            logger.info('User ' + current_user.email + ' sent invalid request to edit notes: ' + str(id))
            return redirect(url_for('edit_notes', id=id))
        title = html.escape(title)
        notes = html.escape(notes)
        existing = models.Resource.query.filter_by(folder=resource.folder, title=title).first()
        if existing and existing.id != id:
            flash('Title already exists in folder', 'danger')
            logger.info('User ' + current_user.email + ' sent invalid request to edit notes: ' + str(id))
            return redirect(url_for('edit_notes', id=id))
        resource.title = title
        resource.data = notes
        Keywords = models.Keywords.query.filter_by(resource=id).all()
        for keyword in Keywords:
            db.session.delete(keyword)
        queue = models.Queue.query.filter_by(resource=id).first()
        if queue:
            db.session.delete(queue)
        db.session.commit()
        flash("Notes edited", "success")
        logger.info('User ' + current_user.email + ' edited notes: ' + str(id))
        return redirect(url_for('folder', id=resource.folder))
    else:
        flash('Error editing notes', 'danger')
        logger.info('User ' + current_user.email + ' sent invalid request to edit notes: ' + str(id))
        return redirect(url_for('folder', id=resource.folder))

"""
Get all resources in a folder with user or admin type
For ajax requests
User must be logged in
Get Request Only
Parameters:
  folder: id of folder to get resources from
  type: type of resources to get (user or admin)
Returns:
  HTML to be inserted into page
Check if folder and type are valid
Check if folder exists
Check if parent group exists
Check if user has permission to view folder
Get all resources in folder of specified type (if admin, ignore hidden value)
Sum & average all reviews for each resource
Render template with resources
"""
@app.route('/resources', methods=['GET'])
@login_required
def resources():
    if request.args.get('folder') is None or not request.args.get('folder').isdigit():
        logger.info('User ' + current_user.email + ' sent invalid request to view resources')
        return 'Missing or Invalid folder'
    id = int(request.args.get('folder'))
    if request.args.get('type') is None:
        logger.info('User ' + current_user.email + ' sent invalid request to view resources')
        return 'Missing or Invalid tab'
    type = str(request.args.get('type'))
    folder = models.Folder.query.filter_by(id=id).first()
    if not folder:
        logger.info('User ' + current_user.email + ' sent invalid request to view resources')
        return 'Missing or Invalid folder'
    group = models.Group.query.filter_by(id=folder.group).first()
    if not group:
        logger.info('User ' + current_user.email + ' sent invalid request to view resources')
        return 'Missing or Invalid folder'
    if group.owner != current_user.id and not models.Member.query.filter_by(user=current_user.id, group=group.id).first():
        logger.warning('User ' + current_user.email + ' tried to view resources without permission')
        return 'Missing or Invalid folder'
    if type != "Admin" and type != "User":
        logger.info('User ' + current_user.email + ' sent invalid request to view resources')
        return 'Missing or Invalid tab'
    if type == "Admin":
        resources = models.Resource.query.filter_by(folder=id, creator=group.owner).all()
    elif type == "User":
        resources = models.Resource.query.filter_by(folder=id).filter(models.Resource.creator != group.owner).all()
    if not resources:
        logger.info('User ' + current_user.email + ' tried to view resources but found none of type ' + type + " in folder " + str(id))
        return 'No resources found'
    dictratings = {}
    dictkeywords = {}
    for resource in resources:
        ratings = models.Review.query.filter_by(resource=resource.id).all()
        if ratings:
            dictratings[int(resource.id)] = str(sum(rating.rating for rating in ratings) / len(ratings)) + "/5"
        else:
            dictratings[int(resource.id)] = "NA"
        keywords = models.Keywords.query.filter_by(resource=resource.id).first()
        if keywords:
            dictkeywords[int(resource.id)] = json.loads(keywords.json)
        else:
            dictkeywords[int(resource.id)] = []
    logger.info('User ' + current_user.email + ' viewed resources in folder ' + str(id) + "with type " + type )
    return render_template('resources.html', resources=resources, ratings=dictratings, keywords=dictkeywords)

"""
Get specific resource page
User must be logged in
Get Request Only
Parameters:
  id: id of resource to get
Returns:
  Resource page
Check if resource exists
Check if folder exists
Check if parent group exists
Check if user has permission to view folder
Get all reviews for resource and generate their delete forms
Sum & average all reviews for resource
Render template with resource
"""
@app.route('/resource/<id>', methods=['GET'])
@login_required
def resource(id):
    resource = models.Resource.query.filter_by(id=id).first()
    if not resource:
        logger.info('User ' + current_user.email + ' sent invalid request to view resource ' + str(id))
        flash("Resource not found", "danger")
        return redirect(url_for('index'))
    folder = models.Folder.query.filter_by(id=resource.folder).first()
    if not folder:
        logger.info('User ' + current_user.email + ' sent invalid request to view resource ' + str(id) + " with missing folder")
        flash("Resource not found", "danger")
        return redirect(url_for('index'))
    group = models.Group.query.filter_by(id=folder.group).first()
    if not group:
        logger.info('User ' + current_user.email + ' sent invalid request to view resource ' + str(id) + " with missing group")
        flash("Resource not found", "danger")
        return redirect(url_for('index'))
    if group.owner != current_user.id and not models.Member.query.filter_by(user=current_user.id, group=group.id).first():
        logger.warning('User ' + current_user.email + ' tried to view resource without permission')
        flash("You do not have permission to view this resource", "danger")
        return redirect(url_for('index'))
    form = DelResourceForm()
    form.resource_id.data = id
    logger.info('User ' + current_user.email + ' viewed resource ' + str(id))
    reviews = models.Review.query.filter_by(resource=id).all()
    delForms = {}
    if reviews:
        rating = str(sum(review.rating for review in reviews) / len(reviews)) + "/5"
    else:
        rating = "No Ratings"
    already_reviewed = models.Review.query.filter_by(resource=id, creator=current_user.id).first()
    dbKeywords = models.Keywords.query.filter_by(resource=id).first()
    if not dbKeywords:
        keywords = None
    else:
        keywords = json.loads(dbKeywords.json)
    return render_template('resource.html', resource=resource, group=group, folder=folder, form=form, reviews=reviews, rating=rating, keywords=keywords)

"""
Download specific resource
User must be logged in
Get Request Only
Check if resource exists
Check if folder exists
Check if parent group exists
Check if user has permission to download
Download resource
"""
@app.route('/resource/download/<id>', methods=['GET'])
@login_required
def download_resource(id):
    id = int(id)
    resource = models.Resource.query.filter_by(id=id).first()
    if not resource:
        logger.info('User ' + current_user.email + ' sent invalid request to download resource ' + str(id))
        flash("Invalid request", "danger")
        return redirect(url_for('index'))
    folder = models.Folder.query.filter_by(id=resource.folder).first()
    if not folder:
        logger.info('User ' + current_user.email + ' sent invalid request to download resource ' + str(id) + " with missing folder")
        flash("Invalid request", "danger")
        return redirect(url_for('index'))
    group = models.Group.query.filter_by(id=folder.group).first()
    if not group:
        logger.info('User ' + current_user.email + ' sent invalid request to download resource ' + str(id) + " with missing group")
        flash("Invalid request", "danger")
        return redirect(url_for('index'))
    if group.owner != current_user.id and not models.Member.query.filter_by(user=current_user.id, group=group.id).first():
        logger.warning('User ' + current_user.email + ' tried to download resource without permission')
        flash("You do not have permission to download this resource", "danger")
        return redirect(url_for('index'))
    logger.info('User ' + current_user.email + ' downloaded resource ' + str(id))
    return send_file(resource.data[4:], as_attachment=True)

"""
Delete specific resource
User must be logged in
Post Request Only
If form is valid:
  Check if resource exists
  Check if folder exists
  Check if parent group exists
  Check if user has permission to delete
  Delete resource
  Delete all reviews for resource
  Delete all files for resource
  Delete resource
  Log action
  Redirect to folder page
Else:
  Log invalid request
  Flash error
  Redirect to index
"""
@app.route('/resource/delete', methods=['POST'])
@login_required
def delete_resource():
    form = DelResourceForm()
    if form.validate_on_submit():
        resource = models.Resource.query.filter_by(id=form.resource_id.data).first()
        if not resource:
            logger.info('User ' + current_user.email + ' sent invalid request to delete resource ' + str(form.resource_id.data))
            flash("Invalid request", "danger")
            return redirect(url_for('index'))
        folder = models.Folder.query.filter_by(id=resource.folder).first()
        if not folder:
            logger.info('User ' + current_user.email + ' sent invalid request to delete resource ' + str(form.resource_id.data) + " with missing folder")
            flash("Invalid request", "danger")
            return redirect(url_for('index'))
        group = models.Group.query.filter_by(id=folder.group).first()
        if not group:
            logger.info('User ' + current_user.email + ' sent invalid request to delete resource ' + str(form.resource_id.data) + " with missing group")
            flash("Invalid request", "danger")
            return redirect(url_for('index'))
        if resource.creator != current_user.id and group.owner != current_user.id:
            logger.warning('User ' + current_user.email + ' tried to delete resource without permission')
            flash("You do not have permission to delete this resource", "danger")
            return redirect(url_for('index'))
        reviews = models.Review.query.filter_by(resource=form.resource_id.data).all()
        for review in reviews:
            db.session.delete(review)
        keywords = models.Keywords.query.filter_by(resource=form.resource_id.data).first()
        if keywords:
            db.session.delete(keywords)
        if resource.type == "material" or resource.type == "transcript":
            os.remove(resource.data)
        db.session.delete(resource)
        db.session.commit()
        logger.info('User ' + current_user.email + ' deleted resource ' + str(form.resource_id.data))
        flash("Resource deleted", "success")
        return redirect(url_for('folder', id=folder.id))
    else:
        logger.info('User ' + current_user.email + ' sent invalid request to delete resource ' + str(form.resource_id.data))
        flash("Invalid request", "danger")
        return redirect(url_for('index'))

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
        resources = models.Resource.query.filter_by(folder=form.folder_id.data).all()
        for resource in resources:
            reviews = models.Review.query.filter_by(resource=resource.id).all()
            for review in reviews:
                db.session.delete(review)
            keywords = models.Keywords.query.filter_by(resource=resource.id).first()
            db.session.delete(keywords)
            if resource.type == "material" or resource.type == "transcript":
                os.remove(resource.data)
            db.session.delete(resource)
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
            resources = models.Resource.query.filter_by(folder=folder.id).all()
            for resource in resources:
                reviews = models.Review.query.filter_by(resource=resource.id).all()
                for review in reviews:
                    db.session.delete(review)
                keywords = models.Keywords.query.filter_by(resource=resource.id).first()
                if resource.type == "material" or resource.type == "transcript":
                    os.remove(resource.data)
                db.session.delete(resource)
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
        folders = models.Folder.query.filter_by(group=id).all()
        for folder in folders:
            resources = models.Resource.query.filter_by(folder=folder.id).first()
            for resource in resources:
                if resource.creator == current_user.id:
                    reviews = models.Review.query.filter_by(resource=resource.id).all()
                    for review in reviews:
                        db.session.delete(review)
                    keywords = models.Keywords.query.filter_by(resource=resource.id).first()
                    db.session.delete(keywords)
                    if resource.type == "material" or resource.type == "transcript":
                        os.remove(resource.data)
                    db.session.delete(resource)
                else:
                    reviews = models.Review.query.filter_by(resource=resource.id, user=current_user.id).all()
                    for review in reviews:
                        db.session.delete(review)
        db.session.commit()
        logger.info('User ' + current_user.email + ' left group ' + str(id))
        flash("You have left the group", "success")
        return redirect(url_for('index'))
    else:
        logger.info('User ' + current_user.email + ' sent invalid request to leave group ' + str(form.group_id.data))
        flash("Invalid request", "danger")
        return redirect(url_for('index'))