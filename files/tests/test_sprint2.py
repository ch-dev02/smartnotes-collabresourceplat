import pytest
from app import app as flask_app, db, models, mail
from datetime import datetime, timedelta
from flask_mail import Mail
import logging
from test_sprint1 import verify, signup, login
import io
import os

@pytest.fixture
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

# Reusable Scripts
def create_group(client, title):
    return client.post('/create-group', data=dict(title=title), follow_redirects=True)

def join_group(client, code):
    return client.post('/join-group', data=dict(code=code), follow_redirects=True)

def delete_group(client, id):
    return client.post('/group/delete', data=dict(group_id=id), follow_redirects=True)

def leave_group(client, id):
    return client.post('/group/leave', data=dict(group_id=id), follow_redirects=True)

def create_folder(client, group_id, title):
    return client.post('/folder/create', data=dict(group_id=group_id, title=title), follow_redirects=True)

def delete_folder(client, folder_id):
    return client.post('/folder/delete', data=dict(folder_id=folder_id), follow_redirects=True)

def delete_resource(client, resource_id):
    return client.post('/resource/delete', data=dict(resource_id=resource_id), follow_redirects=True)

"""
Test Create Group Variantions:
1. Empty Title
2. Valid Title
"""
def test_create_group(app, client):
    # Empty Title
    signup(client, "smartnotes_uol@protonmail.com", "Password1", "Password1", True, True)
    with app.app_context():
        user = models.User.query.filter_by(email="smartnotes_uol@protonmail.com").first()
    verify(client, user.id)
    login(client, "smartnotes_uol@protonmail.com", "Password1")
    res1 = create_group(client, "")
    assert b"Error creating group" in res1.data

    res2 = create_group(client, "Test Group")
    assert b"Group created successfully" in res2.data
    assert res2.status_code == 200

    # Tear Down: Remove any modification
    with app.app_context():
        db.session.delete(user)
        group = models.Group.query.filter_by(title="Test Group", owner=user.id).first()
        db.session.delete(group)
        db.session.commit()

"""
Test Join Group Variantions:
1. Empty Code
2. Invalid Code
3. Valid Code
"""
def test_join_group(app, client):
    signup(client, "smartnotes_uol@protonmail.com", "Password1", "Password1", True, True)
    with app.app_context():
        user = models.User.query.filter_by(email="smartnotes_uol@protonmail.com").first()
    verify(client, user.id)
    login(client, "smartnotes_uol@protonmail.com", "Password1")
    create_group(client, "Test Group")
    with app.app_context():
        group = models.Group.query.filter_by(title="Test Group", owner=user.id).first()
    
    client.get('/logout')
    signup(client, "charrison16082002@gmail.com", "Password2", "Password2", True, True)
    with app.app_context():
        user2 = models.User.query.filter_by(email="charrison16082002@gmail.com").first()
    verify(client, user2.id)
    login(client, "charrison16082002@gmail.com", "Password2")

    res1 = join_group(client, "")
    assert b"Error joining group" in res1.data

    res2 = join_group(client, group.code+"aaa")
    assert b"Error joining group" in res2.data

    res3 = join_group(client, group.code)
    assert b"Joined group successfully" in res3.data
    with app.app_context():
        membership = models.Member.query.filter_by(user=user2.id, group=group.id).first()
    assert membership is not None

    # Tear Down: Remove any modifications
    with app.app_context():
        db.session.delete(user)
        db.session.delete(user2)
        db.session.delete(group)
        db.session.delete(membership)
        db.session.commit()

"""
Test Delete Group Variantions:
1. No Group ID
2. Invalid Group ID
3. Valid Group ID - Not Owner
4. Valid Group ID - Owner
"""
def test_delete_group(app, client):
    signup(client, "smartnotes_uol@protonmail.com", "Password1", "Password1", True, True)
    with app.app_context():
        user = models.User.query.filter_by(email="smartnotes_uol@protonmail.com").first()
    verify(client, user.id)
    login(client, "smartnotes_uol@protonmail.com", "Password1")
    create_group(client, "Test Group")
    with app.app_context():
        group = models.Group.query.filter_by(title="Test Group", owner=user.id).first()

    res1 = delete_group(client, "")
    assert b"Invalid request" in res1.data

    res2 = delete_group(client, -1 * group.id)
    print(res2.data)
    assert b"Invalid request, this group" in res2.data

    with app.app_context():
        group.owner = user.id+1
        db.session.commit()

    client.get('/logout')
    signup(client, "charrison16082002@gmail.com", "Password1", "Password1", True, True)
    with app.app_context():
        user2 = models.User.query.filter_by(email="charrison16082002@gmail.com").first()
    verify(client, user2.id)
    login(client, "charrison16082002@gmail.com", "Password1")
    res3 = delete_group(client, group.id)
    assert b"You cannot delete a group you do not own." in res3.data

    client.get('/logout')
    login(client, "smartnotes_uol@protonmail.com", "Password1")
    res4 = delete_group(client, group.id)
    assert b"You have deleted the group" in res4.data

    # Tear Down: Remove any modifications
    with app.app_context():
        db.session.delete(user)
        db.session.delete(user2)
        db.session.commit()

"""
Test Leave Group Variantions:
1. No Group ID
2. Invalid Group ID
3. Valid Group ID - Not Member
4. Valid Group ID - Member
5. Valid Group ID - Owner
"""
def test_leave_group(app, client):
    signup(client, "smartnotes_uol@protonmail.com", "Password1", "Password1", True, True)
    with app.app_context():
        user = models.User.query.filter_by(email="smartnotes_uol@protonmail.com").first()
    verify(client, user.id)
    login(client, "smartnotes_uol@protonmail.com", "Password1")
    create_group(client, "Test Group")
    with app.app_context():
        group = models.Group.query.filter_by(title="Test Group", owner=user.id).first()
    client.get('/logout')

    signup(client, "charrison16082002@gmail.com", "Password1", "Password1", True, True)
    with app.app_context():
        user2 = models.User.query.filter_by(email="charrison16082002@gmail.com").first()
    verify(client, user2.id)
    login(client, "charrison16082002@gmail.com", "Password1")

    res1 = leave_group(client, "")
    assert b"Invalid request" in res1.data

    res2 = leave_group(client, -1 * group.id)
    assert b"Invalid request, this group" in res2.data    

    res3 = leave_group(client, group.id)
    assert b"Invalid request, you are not a member of this group" in res3.data

    join_group(client, group.code)
    with app.app_context():
        membership = models.Member.query.filter_by(user=user2.id, group=group.id).first()
    assert membership is not None
    res4 = leave_group(client, group.id)
    assert b"You have left the group" in res4.data
    with app.app_context():
        membership = models.Member.query.filter_by(user=user2.id, group=group.id).first()
    assert membership is None

    client.get('/logout')
    login(client, "smartnotes_uol@protonmail.com", "Password1")
    res5 = leave_group(client, group.id)
    assert b"You cannot leave a group you own, you may delete it instead." in res5.data

    # Tear Down: Remove any modifications
    with app.app_context():
        db.session.delete(user)
        db.session.delete(user2)
        db.session.delete(group)
        db.session.commit()

"""
Test Create Folder Variations:
1. No Parent Group Specified
2. Invalid Parent Group Specified
3. Not parent group owner
4. Parent group owner, Missing Folder name
5. Parent group owner and folder name (Valid)
"""
def test_create_folder(app, client):
    signup(client, "smartnotes_uol@protonmail.com", "Password1", "Password1", True, True)
    signup(client, "charrison16082002@gmail.com", "Password1", "Password1", True, True)
    with app.app_context():
        user = models.User.query.filter_by(email="smartnotes_uol@protonmail.com").first()
        user2 = models.User.query.filter_by(email="charrison16082002@gmail.com").first()
    verify(client, user.id)
    verify(client, user2.id)

    login(client, "smartnotes_uol@protonmail.com", "Password1")
    create_group(client, "Test Group")
    with app.app_context():
        group = models.Group.query.filter_by(title="Test Group", owner=user.id).first()
    
    res1 = create_folder(client, "", "Test Folder")
    assert b"Error creating folder" in res1.data

    res2 = create_folder(client, -1 * group.id, "Test Folder")
    assert b"Group doesn" in res2.data

    client.get('/logout')
    login(client, "charrison16082002@gmail.com", "Password1")
    res3 = create_folder(client, group.id, "Test Folder")
    assert b"have permission to create folders in this group" in res3.data

    client.get('/logout')
    login(client, "smartnotes_uol@protonmail.com", "Password1")
    res4 = create_folder(client, group.id, "")
    assert b"Error creating folder" in res4.data

    res5 = create_folder(client, group.id, "Test Folder")
    assert b"Folder created successfully" in res5.data
    with app.app_context():
        folder = models.Folder.query.filter_by(title="Test Folder", group=group.id).first()
    assert folder is not None

    # Tear Down: Remove any modifications
    with app.app_context():
        db.session.delete(user)
        db.session.delete(user2)
        db.session.delete(group)
        db.session.delete(folder)
        db.session.commit()

"""
Test Delete Folder Variations:
1. No Folder ID
2. Invalid Folder ID
3. Not Folder's Group Owner
4. Folder's Group Owner, 
"""
def test_delete_folder(app, client):
    signup(client, "smartnotes_uol@protonmail.com", "Password1", "Password1", True, True)
    signup(client, "charrison16082002@gmail.com", "Password1", "Password1", True, True)
    with app.app_context():
        user = models.User.query.filter_by(email="smartnotes_uol@protonmail.com").first()
        user2 = models.User.query.filter_by(email="charrison16082002@gmail.com").first()
    verify(client, user.id)
    verify(client, user2.id)

    login(client, "smartnotes_uol@protonmail.com", "Password1")
    create_group(client, "Test Group")
    with app.app_context():
        group = models.Group.query.filter_by(title="Test Group", owner=user.id).first()
    
    create_folder(client, group.id, "Test Folder")
    with app.app_context():
        folder = models.Folder.query.filter_by(title="Test Folder", group=group.id).first()

    res1 = delete_folder(client, "")
    assert b"Invalid request" in res1.data

    res2 = delete_folder(client, -1 * folder.id)
    assert b"Invalid request" in res2.data

    client.get('/logout')
    login(client, "charrison16082002@gmail.com", "Password1")
    res3 = delete_folder(client, folder.id)
    assert b"You do not have permission to delete this folder" in res3.data

    client.get('/logout')
    login(client, "smartnotes_uol@protonmail.com", "Password1")
    res4 = delete_folder(client, folder.id)
    assert b"Folder deleted" in res4.data
    with app.app_context():
        folder = models.Folder.query.filter_by(title="Test Folder", group=group.id).first()
    assert folder is None

    # Tear Down: Remove any modifications
    with app.app_context():
        db.session.delete(user)
        db.session.delete(user2)
        db.session.delete(group)
        db.session.commit()

"""
Test Add Url Variations:
1. No Parent Folder Specified
2. Invalid Parent Folder Specified
3. Not In Group
4. In Group, Missing Url
5. In Group, Invalid Url
6. In Group, Missing Title
7. In Group and Valid
8. In Group, Url already exists
"""
def test_add_url(app, client):

    def add_url(client, folder_id, url, title):
        return client.post('/add_url', data=dict(url=url, title=title), query_string=dict(folder=folder_id), follow_redirects=True)

    signup(client, "smartnotes_uol@protonmail.com", "Password1", "Password1", True, True)
    signup(client, "charrison16082002@gmail.com", "Password1", "Password1", True, True)
    with app.app_context():
        user = models.User.query.filter_by(email="smartnotes_uol@protonmail.com").first()
        user2 = models.User.query.filter_by(email="charrison16082002@gmail.com").first()
    verify(client, user.id)
    verify(client, user2.id)

    login(client, "smartnotes_uol@protonmail.com", "Password1")
    create_group(client, "Test Group")
    with app.app_context():
        group = models.Group.query.filter_by(title="Test Group", owner=user.id).first()
    
    create_folder(client, group.id, "Test Folder")
    with app.app_context():
        folder = models.Folder.query.filter_by(title="Test Folder", group=group.id).first()

    res1 = add_url(client, "", "https://www.google.com", "Google")
    assert b"Invalid request" in res1.data

    res2 = add_url(client, 0, "https://www.google.com", "Google")
    assert b"Folder doesn" in res2.data

    client.get('/logout')
    login(client, "charrison16082002@gmail.com", "Password1")
    res3 = add_url(client, folder.id, "https://www.google.com", "Google")
    assert b"t have permission to add URLs to this folder" in res3.data

    client.get('/logout')
    login(client, "smartnotes_uol@protonmail.com", "Password1")
    res4 = add_url(client, folder.id, "", "Google")
    assert b"Error adding URL" in res4.data

    res5 = add_url(client, folder.id, "htp:/ww.googlecom", "Google")
    assert b"Invalid URL" in res5.data

    res6 = add_url(client, folder.id, "https://www.google.com", "")
    assert b"Error adding URL" in res6.data

    res7 = add_url(client, folder.id, "https://www.google.com", "Google")
    assert b"URL added" in res7.data
    with app.app_context():
        url = models.Resource.query.filter_by(title="Google", folder=folder.id).first()
    assert url is not None

    res8 = add_url(client, folder.id, "https://www.google.com", "Google")
    assert b"URL already exists in folder" in res8.data

    # Tear Down: Remove any modifications
    with app.app_context():
        db.session.delete(user)
        db.session.delete(user2)
        db.session.delete(group)
        db.session.delete(folder)
        db.session.delete(url)
        db.session.commit()

"""
Test Delete Url Variations:
1. No Resource ID
2. Invalid Resource ID
3. Not Resource's Group Owner or Resource Creator
4. Valid User, Valid Resource
"""
def test_delete_url(app, client):
    signup(client, "smartnotes_uol@protonmail.com", "Password1", "Password1", True, True)
    signup(client, "charrison16082002@gmail.com", "Password1", "Password1", True, True)
    with app.app_context():
        user = models.User.query.filter_by(email="smartnotes_uol@protonmail.com").first()
        user2 = models.User.query.filter_by(email="charrison16082002@gmail.com").first()
    verify(client, user.id)
    verify(client, user2.id)

    login(client, "smartnotes_uol@protonmail.com", "Password1")
    create_group(client, "Test Group")
    with app.app_context():
        group = models.Group.query.filter_by(title="Test Group", owner=user.id).first()
    
    create_folder(client, group.id, "Test Folder")
    with app.app_context():
        folder = models.Folder.query.filter_by(title="Test Folder", group=group.id).first()

    client.post('/add_url', 
                data=dict(url="http://www.google.com", title="Google"), 
                query_string=dict(folder=folder.id),
                follow_redirects=True)
    with app.app_context():
        url = models.Resource.query.filter_by(title="Google", folder=folder.id).first()

    res1 = delete_resource(client, "")
    assert b"Invalid request" in res1.data

    res2 = delete_resource(client, 0)
    assert b"Invalid request" in res2.data

    client.get('/logout')
    login(client, "charrison16082002@gmail.com", "Password1")
    res3 = delete_resource(client, url.id)
    assert b"You do not have permission to delete this resource" in res3.data

    client.get('/logout')
    login(client, "smartnotes_uol@protonmail.com", "Password1")
    res4 = delete_resource(client, url.id)
    assert b"Resource deleted" in res4.data

    # Tear Down: Remove any modifications
    with app.app_context():
        db.session.delete(user)
        db.session.delete(user2)
        db.session.delete(group)
        db.session.delete(folder)
        db.session.commit()

"""
Test Add Notes Variations:
1. No Folder ID
2. Invalid Folder ID
3. Not Folder's Group Owner or Folder Creator
4. No Note Title
5. No Note Content
6. Valid User, Valid Folder, Valid Note Title, Valid Note Content
7. Valid User, Valid Folder, Title Taken, Valid Note Content
"""
def test_add_note(app, client):
    
    def add_notes(client, folder_id, title, notes):
        return client.post('/add_notes', 
                            data=dict(title=title, notes=notes), 
                            query_string=dict(folder=folder_id),
                            follow_redirects=True)

    signup(client, "smartnotes_uol@protonmail.com", "Password1", "Password1", True, True)
    signup(client, "charrison16082002@gmail.com", "Password1", "Password1", True, True)
    with app.app_context():
        user = models.User.query.filter_by(email="smartnotes_uol@protonmail.com").first()
        user2 = models.User.query.filter_by(email="charrison16082002@gmail.com").first()
    verify(client, user.id)
    verify(client, user2.id)

    login(client, "smartnotes_uol@protonmail.com", "Password1")
    create_group(client, "Test Group")
    with app.app_context():
        group = models.Group.query.filter_by(title="Test Group", owner=user.id).first()
    
    create_folder(client, group.id, "Test Folder")
    with app.app_context():
        folder = models.Folder.query.filter_by(title="Test Folder", group=group.id).first()

    res1 = add_notes(client, "", "Test Note", "Test Content")
    assert b"Invalid request" in res1.data

    res2 = add_notes(client, 0, "Test Note", "Test Content")
    assert b"Folder doesn" in res2.data

    client.get('/logout')
    login(client, "charrison16082002@gmail.com", "Password1")
    res3 = add_notes(client, folder.id, "Test Note", "# Test Content")
    assert b"t have permission to add to this folder" in res3.data

    client.get('/logout')
    login(client, "smartnotes_uol@protonmail.com", "Password1")
    res4 = add_notes(client, folder.id, "", "# Test Content")
    assert b"Error adding notes" in res4.data

    res5 = add_notes(client, folder.id, "Test Note", "")
    print(res5.data)
    assert b"Fields cannot be empty" in res5.data

    res6 = add_notes(client, folder.id, "Test Note", "# Test Content")
    assert b"Notes added" in res6.data
    with app.app_context():
        note = models.Resource.query.filter_by(title="Test Note", folder=folder.id).first()
    assert note is not None

    res7 = add_notes(client, folder.id, "Test Note", "# Test Content 2")
    assert b"Title already exists in folder" in res7.data

    # Tear Down: Remove any modifications
    with app.app_context():
        db.session.delete(user)
        db.session.delete(user2)
        db.session.delete(group)
        db.session.delete(folder)
        db.session.delete(note)
        db.session.commit()

"""
Test Delete Notes Variations:
1. No Resource ID
2. Invalid Resource ID
3. Not Resource's Group Owner or Resource Creator
4. Valid User, Valid Resource
"""
def test_delete_note(app, client):
    signup(client, "smartnotes_uol@protonmail.com", "Password1", "Password1", True, True)
    signup(client, "charrison16082002@gmail.com", "Password1", "Password1", True, True)
    with app.app_context():
        user = models.User.query.filter_by(email="smartnotes_uol@protonmail.com").first()
        user2 = models.User.query.filter_by(email="charrison16082002@gmail.com").first()
    verify(client, user.id)
    verify(client, user2.id)

    login(client, "smartnotes_uol@protonmail.com", "Password1")
    create_group(client, "Test Group")
    with app.app_context():
        group = models.Group.query.filter_by(title="Test Group", owner=user.id).first()
    
    create_folder(client, group.id, "Test Folder")
    with app.app_context():
        folder = models.Folder.query.filter_by(title="Test Folder", group=group.id).first()

    client.post('/add_notes', 
                data=dict(title="Test Note", notes="Test Content"), 
                query_string=dict(folder=folder.id),
                follow_redirects=True)
    
    with app.app_context():
        note = models.Resource.query.filter_by(title="Test Note", folder=folder.id).first()

    res1 = delete_resource(client, "")
    assert b"Invalid request" in res1.data

    res2 = delete_resource(client, 0)
    assert b"Invalid request" in res2.data

    client.get('/logout')
    login(client, "charrison16082002@gmail.com", "Password1")
    res3 = delete_resource(client, note.id)
    assert b"You do not have permission to delete this resource" in res3.data

    client.get('/logout')
    login(client, "smartnotes_uol@protonmail.com", "Password1")
    res4 = delete_resource(client, note.id)
    assert b"Resource deleted" in res4.data

    # Tear Down: Remove any modifications
    with app.app_context():
        db.session.delete(user)
        db.session.delete(user2)
        db.session.delete(group)
        db.session.delete(folder)
        db.session.commit()

"""
Test Edit Notes Variations:
1. No Resource ID
2. Invalid Resource ID
3. Not Resource's Group Owner or Resource Creator
4. No Note Title
5. No Note Content
6. Valid User, Valid Resource, Valid Note Title, Valid Note Content
7. Valid User, Valid Resource, Title Taken, Valid Note Content
"""
def test_edit_note(app, client):
    
    def edit_notes(client, folder_id, title, notes):
        return client.post('/edit_notes', 
                            data=dict(title=title, notes=notes), 
                            query_string=dict(id=folder_id),
                            follow_redirects=True)

    signup(client, "smartnotes_uol@protonmail.com", "Password1", "Password1", True, True)
    signup(client, "charrison16082002@gmail.com", "Password1", "Password1", True, True)
    with app.app_context():
        user = models.User.query.filter_by(email="smartnotes_uol@protonmail.com").first()
        user2 = models.User.query.filter_by(email="charrison16082002@gmail.com").first()
    verify(client, user.id)
    verify(client, user2.id)

    login(client, "smartnotes_uol@protonmail.com", "Password1")
    create_group(client, "Test Group")
    with app.app_context():
        group = models.Group.query.filter_by(title="Test Group", owner=user.id).first()
    
    create_folder(client, group.id, "Test Folder")
    with app.app_context():
        folder = models.Folder.query.filter_by(title="Test Folder", group=group.id).first()

    client.post('/add_notes', 
                data=dict(title="Test Note", notes="Test Content"), 
                query_string=dict(folder=folder.id),
                follow_redirects=True)
    client.post('/add_notes', 
                data=dict(title="Test Note Collision", notes="Test Content Collision"), 
                query_string=dict(folder=folder.id),
                follow_redirects=True)
    
    with app.app_context():
        note = models.Resource.query.filter_by(title="Test Note", folder=folder.id).first()
        collision = models.Resource.query.filter_by(title="Test Note Collision", folder=folder.id).first()

    res1 = edit_notes(client, "", "Test Note", "Test Content")
    assert b"Invalid request" in res1.data

    res2 = edit_notes(client, 0, "Test Note", "Test Content")
    assert b"Notes don" in res2.data

    client.get('/logout')
    login(client, "charrison16082002@gmail.com", "Password1")
    join_group(client, group.code)
    with app.app_context():
        member = models.Member.query.filter_by(user=user2.id, group=group.id).first()
    res3 = edit_notes(client, note.id, "Test Note", "# Test Content")
    assert b"t have permission to edit these notes" in res3.data

    client.get('/logout')
    login(client, "smartnotes_uol@protonmail.com", "Password1")
    res4 = edit_notes(client, note.id, "", "# Test Content")
    assert b"Error editing notes" in res4.data

    res5 = edit_notes(client, note.id, "Test Note", "")
    print(res5.data)
    assert b"Fields cannot be empty" in res5.data

    res6 = edit_notes(client, note.id, "Test Note 2", "# Test Content")
    assert b"Notes edited" in res6.data
    with app.app_context():
        note = models.Resource.query.filter_by(title="Test Note 2", folder=folder.id).first()
    assert note is not None

    res7 = edit_notes(client, note.id, "Test Note Collision", "# Test Content 2")
    assert b"Title already exists in folder" in res7.data

    # Tear Down: Remove any modifications
    with app.app_context():
        db.session.delete(user)
        db.session.delete(user2)
        db.session.delete(group)
        db.session.delete(folder)
        db.session.delete(note)
        db.session.delete(collision)
        db.session.delete(member)
        db.session.commit()

"""
Test Add Transcript Variations:
1. No Transcript Title
2. No Transcript File
3. No Folder ID
4. Invalid Folder ID
5. Not Folder's Group Owner
6. Invalid File Type
7. Everything Valid
8. Title Taken
"""
def test_add_transcript(app, client):
    
    def add_transcript(client, folder_id, title, file_name):
        data = {
            'file': (io.BytesIO(b"some initial text data"), file_name),
            'title': title
        }
        return client.post('/upload_transcript',
                            data=data,
                            query_string=dict(folder=folder_id),
                            follow_redirects=True)

    signup(client, "smartnotes_uol@protonmail.com", "Password1", "Password1", True, True)
    signup(client, "charrison16082002@gmail.com", "Password1", "Password1", True, True)
    with app.app_context():
        user = models.User.query.filter_by(email="smartnotes_uol@protonmail.com").first()
        user2 = models.User.query.filter_by(email="charrison16082002@gmail.com").first()
    verify(client, user.id)
    verify(client, user2.id)

    login(client, "smartnotes_uol@protonmail.com", "Password1")
    create_group(client, "Test Group")
    with app.app_context():
        group = models.Group.query.filter_by(title="Test Group", owner=user.id).first()
    
    create_folder(client, group.id, "Test Folder")
    with app.app_context():
        folder = models.Folder.query.filter_by(title="Test Folder", group=group.id).first()

    res1 = add_transcript(client, folder.id, "", "test.txt")
    assert b"Error uploading file" in res1.data

    res2 = add_transcript(client, folder.id, "Test Transcript", "")
    assert b"Error uploading file" in res2.data

    res3 = add_transcript(client, "", "Test Transcript", "test.txt")
    assert b"Invalid request" in res3.data

    res4 = add_transcript(client, 0, "Test Transcript", "test.txt")
    assert b"Folder doesn" in res4.data

    client.get('/logout')
    login(client, "charrison16082002@gmail.com", "Password1")
    res5 = add_transcript(client, folder.id, "Test Transcript", "test.txt")
    assert b"t have permission to add to this folder" in res5.data

    client.get('/logout')
    login(client, "smartnotes_uol@protonmail.com", "Password1")
    res6 = add_transcript(client, folder.id, "Test Transcript", "test.pdf")
    assert b"Invalid file type" in res6.data

    res7 = add_transcript(client, folder.id, "Test Transcript", "test.txt")
    assert b"File uploaded" in res7.data
    with app.app_context():
        transcript = models.Resource.query.filter_by(title="Test Transcript", folder=folder.id).first()
    assert transcript is not None
    assert os.path.exists(transcript.data) == True

    res8 = add_transcript(client, folder.id, "Test Transcript", "test.txt")
    assert b"Resource with that title already exists" in res8.data

    # Tear Down: Remove any modifications
    os.remove(transcript.data)
    with app.app_context():
        db.session.delete(user)
        db.session.delete(user2)
        db.session.delete(group)
        db.session.delete(folder)
        db.session.delete(transcript)
        db.session.commit()

"""
Test Add Material Variations:
1. No Transcript Title
2. No Transcript File
3. No Folder ID
4. Invalid Folder ID
5. Not Folder's Group Owner
6. Invalid File Type
7. Everything Valid
8. Title Taken
"""
def test_add_material(app, client):
    
    def add_material(client, folder_id, title, file_name):
        data = {
            'file': (io.BytesIO(b"some initial text data"), file_name),
            'title': title
        }
        return client.post('/upload_material',
                            data=data,
                            query_string=dict(folder=folder_id),
                            follow_redirects=True)

    signup(client, "smartnotes_uol@protonmail.com", "Password1", "Password1", True, True)
    signup(client, "charrison16082002@gmail.com", "Password1", "Password1", True, True)
    with app.app_context():
        user = models.User.query.filter_by(email="smartnotes_uol@protonmail.com").first()
        user2 = models.User.query.filter_by(email="charrison16082002@gmail.com").first()
    verify(client, user.id)
    verify(client, user2.id)

    login(client, "smartnotes_uol@protonmail.com", "Password1")
    create_group(client, "Test Group")
    with app.app_context():
        group = models.Group.query.filter_by(title="Test Group", owner=user.id).first()
    
    create_folder(client, group.id, "Test Folder")
    with app.app_context():
        folder = models.Folder.query.filter_by(title="Test Folder", group=group.id).first()

    res1 = add_material(client, folder.id, "", "test.pdf")
    assert b"Error uploading file" in res1.data

    res2 = add_material(client, folder.id, "Test Material", "")
    assert b"Error uploading file" in res2.data

    res3 = add_material(client, "", "Test Material", "test.pdf")
    assert b"Invalid request" in res3.data

    res4 = add_material(client, 0, "Test Material", "test.pdf")
    assert b"Folder doesn" in res4.data

    client.get('/logout')
    login(client, "charrison16082002@gmail.com", "Password1")
    res5 = add_material(client, folder.id, "Test Material", "test.pdf")
    assert b"t have permission to add to this folder" in res5.data

    client.get('/logout')
    login(client, "smartnotes_uol@protonmail.com", "Password1")
    res6 = add_material(client, folder.id, "Test Material", "test.txt")
    assert b"Invalid file type" in res6.data

    res7 = add_material(client, folder.id, "Test Material", "test.pdf")
    assert b"File uploaded" in res7.data
    with app.app_context():
        material = models.Resource.query.filter_by(title="Test Material", folder=folder.id).first()
    assert material is not None
    assert os.path.exists(material.data) == True

    res8 = add_material(client, folder.id, "Test Material", "test.pdf")
    assert b"Resource with that title already exists" in res8.data

    # Tear Down: Remove any modifications
    os.remove(material.data)
    with app.app_context():
        db.session.delete(user)
        db.session.delete(user2)
        db.session.delete(group)
        db.session.delete(folder)
        db.session.delete(material)
        db.session.commit()

"""
Test Delete Transcript Variations:
1. No Resource ID
2. Invalid Resource ID
3. Not Resource's Group Owner
4. Everything Valid
"""
def test_delete_transcript(app, client):
    def add_transcript(client, folder_id, title, file_name):
        data = {
            'file': (io.BytesIO(b"some initial text data"), file_name),
            'title': title
        }
        return client.post('/upload_transcript',
                            data=data,
                            query_string=dict(folder=folder_id),
                            follow_redirects=True)

    signup(client, "smartnotes_uol@protonmail.com", "Password1", "Password1", True, True)
    signup(client, "charrison16082002@gmail.com", "Password1", "Password1", True, True)
    with app.app_context():
        user = models.User.query.filter_by(email="smartnotes_uol@protonmail.com").first()
        user2 = models.User.query.filter_by(email="charrison16082002@gmail.com").first()
    verify(client, user.id)
    verify(client, user2.id)

    login(client, "smartnotes_uol@protonmail.com", "Password1")
    create_group(client, "Test Group")
    with app.app_context():
        group = models.Group.query.filter_by(title="Test Group", owner=user.id).first()
    
    create_folder(client, group.id, "Test Folder")
    with app.app_context():
        folder = models.Folder.query.filter_by(title="Test Folder", group=group.id).first()

    add_transcript(client, folder.id, "Test Transcript", "test.txt")
    with app.app_context():
        transcript = models.Resource.query.filter_by(title="Test Transcript", folder=folder.id).first()

    res1 = delete_resource(client, "")
    assert b"Invalid request" in res1.data

    res2 = delete_resource(client, 0)
    assert b"Invalid request" in res2.data

    client.get('/logout')
    login(client, "charrison16082002@gmail.com", "Password1")
    res3 = delete_resource(client, transcript.id)
    assert b"t have permission to delete this resource" in res3.data

    client.get('/logout')
    login(client, "smartnotes_uol@protonmail.com", "Password1")
    res4 = delete_resource(client, transcript.id)
    assert b"Resource deleted" in res4.data
    assert os.path.exists(transcript.data) == False
    with app.app_context():
        transcript = models.Resource.query.filter_by(title="Test Transcript", folder=folder.id).first()
    assert transcript is None

    # Tear Down: Remove any modifications
    with app.app_context():
        db.session.delete(user)
        db.session.delete(user2)
        db.session.delete(group)
        db.session.delete(folder)
        db.session.commit()

"""
Test Delete Material Variations:
1. No Resource ID
2. Invalid Resource ID
3. Not Resource's Group Owner
4. Everything Valid
"""
def test_delete_material(app, client):
    def add_material(client, folder_id, title, file_name):
        data = {
            'file': (io.BytesIO(b"some initial text data"), file_name),
            'title': title
        }
        return client.post('/upload_material',
                            data=data,
                            query_string=dict(folder=folder_id),
                            follow_redirects=True)

    signup(client, "smartnotes_uol@protonmail.com", "Password1", "Password1", True, True)
    signup(client, "charrison16082002@gmail.com", "Password1", "Password1", True, True)
    with app.app_context():
        user = models.User.query.filter_by(email="smartnotes_uol@protonmail.com").first()
        user2 = models.User.query.filter_by(email="charrison16082002@gmail.com").first()
    verify(client, user.id)
    verify(client, user2.id)

    login(client, "smartnotes_uol@protonmail.com", "Password1")
    create_group(client, "Test Group")
    with app.app_context():
        group = models.Group.query.filter_by(title="Test Group", owner=user.id).first()
    
    create_folder(client, group.id, "Test Folder")
    with app.app_context():
        folder = models.Folder.query.filter_by(title="Test Folder", group=group.id).first()

    add_material(client, folder.id, "Test Material", "test.pdf")
    with app.app_context():
        material = models.Resource.query.filter_by(title="Test Material", folder=folder.id).first()

    res1 = delete_resource(client, "")
    assert b"Invalid request" in res1.data

    res2 = delete_resource(client, 0)
    assert b"Invalid request" in res2.data

    client.get('/logout')
    login(client, "charrison16082002@gmail.com", "Password1")
    res3 = delete_resource(client, material.id)
    assert b"t have permission to delete this resource" in res3.data

    client.get('/logout')
    login(client, "smartnotes_uol@protonmail.com", "Password1")
    res4 = delete_resource(client, material.id)
    assert b"Resource deleted" in res4.data
    assert os.path.exists(material.data) == False
    with app.app_context():
        material = models.Resource.query.filter_by(title="Test Material", folder=folder.id).first()
    assert material is None

    # Tear Down: Remove any modifications
    with app.app_context():
        db.session.delete(user)
        db.session.delete(user2)
        db.session.delete(group)
        db.session.delete(folder)
        db.session.commit()
