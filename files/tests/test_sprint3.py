import pytest
import os
os.environ["TESTING"] = "1"
from app import app as flask_app, db, models, mail
del os.environ["TESTING"]
from flask_mail import Mail
import logging
from test_sprint1 import verify, signup, login
from test_sprint2 import create_group, join_group, delete_group, leave_group, create_folder, delete_folder, delete_resource
import time

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

def add_url(client, folder_id, url, title):
    return client.post('/add_url', data=dict(url=url, title=title), query_string=dict(folder=folder_id), follow_redirects=True)

def add_notes(client, title, notes, folder_id):
    return client.post('/add_notes', data=dict(title=title, notes=notes), query_string=dict(folder=folder_id), follow_redirects=True)

def review_resource(client, resource_id, rating, review):
    return client.post('/review',
                        data=dict(resource_id=resource_id, rating=rating, review=review),
                        follow_redirects=True)

def extract(client, resource_id):
    return client.post('/generate', data=dict(resource_id=resource_id), follow_redirects=True)

"""
Test Group Search Tool
1. No Search Query
2. No Group ID
3. Invalid Group ID
4. Valid, No Results
5, Valid, With Results from 2 folders
6. Valid, With Results from 1 folder
"""
def test_group_search(app, client):

    def search_group(client, query, group_id):
        return client.get('/group/search', query_string=dict(query=query, group_id=group_id), follow_redirects=True)

    signup(client, "smartnotes_uol@protonmail.com", "Password1!", "Password1!", True, True)
    with app.app_context():
        user = models.User.query.filter_by(email="smartnotes_uol@protonmail.com").first()
    verify(client, user.id)

    # Create A Group with a folder
    login(client, "smartnotes_uol@protonmail.com", "Password1!")
    create_group(client, "Test Group")
    with app.app_context():
        group = models.Group.query.filter_by(title="Test Group").first()
    create_folder(client, group.id, "Test Folder")
    create_folder(client, group.id, "Test Folder 2")
    with app.app_context():
        folder = models.Folder.query.filter_by(title="Test Folder").first()
        folder2 = models.Folder.query.filter_by(title="Test Folder 2").first()

    # Add a notes resource
    add_notes(client, "Elimination NoStem", "# Heading \n ## Subheading", folder.id)
    add_notes(client, "Eliminator", "# Heading2 \n ## Subheading2", folder2.id)
    with app.app_context():
        resource = models.Resource.query.filter_by(title="Elimination NoStem", folder=folder.id).first()
        resource2 = models.Resource.query.filter_by(title="Eliminator", folder=folder2.id).first()

    res1 = search_group(client, "", group.id)
    assert b"No resources found" in res1.data

    res2 = search_group(client, "Gaussian", 0)
    assert b"No resources found" in res2.data

    res3 = search_group(client, "Gaussian", 999)
    assert b"No resources found" in res3.data

    res4 = search_group(client, "Gaussian", group.id)
    assert b"No resources found" in res4.data

    res5 = search_group(client, "Elimination", group.id)
    assert b"Elimination" in res5.data
    assert b"Eliminator" in res5.data

    res6 = search_group(client, "NoStem", group.id)
    assert b"Elimination" in res6.data
    assert b"Eliminator" not in res6.data

    # Tear Down
    with app.app_context():
        db.session.delete(group)
        db.session.delete(user)
        db.session.delete(resource)
        db.session.delete(resource2)
        st = models.SearchTree.query.filter_by(folder=folder.id).first()
        db.session.delete(st)
        db.session.delete(folder)
        st2 = models.SearchTree.query.filter_by(folder=folder2.id).first()
        db.session.delete(st2)
        db.session.delete(folder2)
        db.session.commit()

"""
Test Folder Search Tool
1. No Search Query
2. No Folder ID
3. Invalid Folder ID
4. Valid, No Results
5. Valid, With Results (Matching Title)
6. Valid, With Results (Matching Stem of Title)
"""
def test_folder_search(app, client):

    def search_folder(client, query, folder_id):
        return client.get('/folder/search', query_string=dict(query=query, folder_id=folder_id), follow_redirects=True)

    signup(client, "smartnotes_uol@protonmail.com", "Password1!", "Password1!", True, True)
    with app.app_context():
        user = models.User.query.filter_by(email="smartnotes_uol@protonmail.com").first()
    verify(client, user.id)

    # Create A Group with a folder
    login(client, "smartnotes_uol@protonmail.com", "Password1!")
    create_group(client, "Test Group")
    with app.app_context():
        group = models.Group.query.filter_by(title="Test Group").first()
    create_folder(client, group.id, "Test Folder")
    with app.app_context():
        folder = models.Folder.query.filter_by(title="Test Folder").first()

    # Add a notes resource
    add_notes(client, "Elimination", "# Heading \n ## Subheading", folder.id)
    with app.app_context():
        resource = models.Resource.query.filter_by(title="Elimination", folder=folder.id).first()
    
    res1 = search_folder(client, "", folder.id)
    assert b"No resources found" in res1.data

    res2 = search_folder(client, "Gaussian", 0)
    assert b"No resources found" in res2.data

    res3 = search_folder(client, "Gaussian", 999)
    assert b"No resources found" in res3.data

    res4 = search_folder(client, "Gaussian", folder.id)
    assert b"No resources found" in res4.data

    res5 = search_folder(client, "Elimination", folder.id)
    assert b"Elimination" in res5.data

    res6 = search_folder(client, "Eliminator", folder.id)
    assert b"Elimination" in res6.data

    # Tear Down
    with app.app_context():
        db.session.delete(user)
        db.session.delete(group)
        st = models.SearchTree.query.filter_by(folder=folder.id).first()
        db.session.delete(st)
        db.session.delete(folder)
        db.session.delete(resource)
        db.session.commit()

"""
Test Keyword Extractor:
1. No Resource ID
2. Invalid Resource ID
3. Valid
4. Invalid, Already Generated
"""
def test_extractor_interface(app, client):
    signup(client, "smartnotes_uol@protonmail.com", "Password1!", "Password1!", True, True)
    with app.app_context():
        user = models.User.query.filter_by(email="smartnotes_uol@protonmail.com").first()
    verify(client, user.id)

    # Create A Group with a folder
    login(client, "smartnotes_uol@protonmail.com", "Password1!")
    create_group(client, "Test Group")
    with app.app_context():
        group = models.Group.query.filter_by(title="Test Group").first()
    create_folder(client, group.id, "Test Folder")
    with app.app_context():
        folder = models.Folder.query.filter_by(title="Test Folder").first()
        
    # Add a notes resource
    # Using notes makes keywords predictable
    add_notes(client, "Test Notes", "# Test Notes \n ## Subtitle", folder.id)
    with app.app_context():
        resource = models.Resource.query.filter_by(title="Test Notes", folder=folder.id).first()

    res1 = extract(client, "")
    assert b"Invalid form!" in res1.data

    res2 = extract(client, 9999)
    assert b"Resource not found!" in res2.data

    res3 = extract(client, resource.id)
    assert b"Resource queued for keyword generation!" in res3.data
    with app.app_context():
        q = models.Queue.query.filter_by(resource=resource.id).first()
        assert q is not None
    # Cannot run celery task in testing environment
    # So we will manually add the keywords to the database
    keywords = models.Keywords(resource=resource.id, json='["Test Notes", "Subtitle"]')
    with app.app_context():
        db.session.add(keywords)
        db.session.delete(q)
        db.session.commit()

    res4 = extract(client, resource.id)
    assert b"Keywords already generated!" in res4.data
    with app.app_context():
        q = models.Queue.query.filter_by(resource=resource.id).first()
        assert q is None
    
    # Tear Down
    with app.app_context():
        db.session.delete(keywords)
        db.session.delete(resource)
        st = models.SearchTree.query.filter_by(folder=folder.id).first()
        db.session.delete(st)
        db.session.delete(folder)
        db.session.delete(group)
        db.session.delete(user)
        db.session.commit()

"""
Test Review Resource:
1. No Resource ID
2. Invalid Resource ID
3. Invalid, Comment is Too Long (> 256 Characters)
4. Invalid, Rating is Not an Integer
5. Invalid, Rating is Not Between 1 and 5
6. Valid
7. Invalid, Already Reviewed
8. Invalid, Resource's Creator
"""
def test_review_resource(app, client):
    # Create 2 Users, Admin and Member
    signup(client, "smartnotes_uol@protonmail.com", "Password1!", "Password1!", True, True)
    signup(client, "charrison16082002@gmail.com", "Password1!", "Password1!", True, True)
    with app.app_context():
        user1 = models.User.query.filter_by(email="smartnotes_uol@protonmail.com").first()
        user2 = models.User.query.filter_by(email="charrison16082002@gmail.com").first()
    verify(client, user1.id)
    verify(client, user2.id)

    # Create A Group with a folder
    login(client, "smartnotes_uol@protonmail.com", "Password1!")
    create_group(client, "Test Group")
    with app.app_context():
        group = models.Group.query.filter_by(title="Test Group", owner=user1.id).first()
    create_folder(client, group.id, "Test Folder")
    with app.app_context():
        folder = models.Folder.query.filter_by(title="Test Folder", group=group.id).first()

    # Member Joins Group
    client.get('/logout')
    login(client, "charrison16082002@gmail.com", "Password1!")
    join_group(client, group.code)
    with app.app_context():
        member = models.Member.query.filter_by(user=user2.id, group=group.id).first()

    # Add a URL
    add_url(client, folder.id, "https://www.google.com", "Google")
    with app.app_context():
        resource = models.Resource.query.filter_by(title="Google", folder=folder.id).first()
    
    # Test Create Review
    client.get('/logout')
    login(client, "smartnotes_uol@protonmail.com", "Password1!")
    res1 = review_resource(client, "", 5, "Test Review")
    assert b"Invalid form!" in res1.data

    res2 = review_resource(client, 9999, 5, "Test Review")
    assert b"Resource not found!" in res2.data

    res3 = review_resource(client, resource.id, 5, "a" * 300)
    assert b"Comment too long!" in res3.data

    res4 = review_resource(client, resource.id, "a", "Test Review")
    assert b"Invalid form!" in res4.data
    
    res5 = review_resource(client, resource.id, 6, "Test Review")
    assert b"Invalid form!" in res5.data

    res6 = review_resource(client, resource.id, 5, "Test Review")
    assert b"Review created!" in res6.data
    with app.app_context():
        review = models.Review.query.filter_by(resource=resource.id, creator=user1.id).first()
    assert review is not None
    assert review.rating == 5
    assert review.comment == "Test Review"

    res7 = review_resource(client, resource.id, 2, "Test Review Dupe")
    assert b"You have already reviewed this resource!" in res7.data

    client.get('/logout')
    login(client, "charrison16082002@gmail.com", "Password1!")
    res8 = review_resource(client, resource.id, 5, "Test Review")
    assert b"You cannot review your own resource!" in res8.data

    # Tear Down
    with app.app_context():
        db.session.delete(review)
        db.session.delete(resource)
        st = models.SearchTree.query.filter_by(folder=folder.id).first()
        db.session.delete(st)
        db.session.delete(folder)
        db.session.delete(group)
        db.session.delete(member)
        db.session.delete(user1)
        db.session.delete(user2)
        db.session.commit()

"""
Test Delete Review:
1. No Review ID
2. Invalid Review ID
3. Invalid, Not Review's Creator / Group Owner
4. Valid
"""
def test_delete_review(app, client):

    def delete_review(client, review_id):
        return client.post('/review/delete', data=dict(review_id=review_id), follow_redirects=True)

    # Create 3 Users, Admin and 2xMember
    signup(client, "smartnotes_uol@protonmail.com", "Password1!", "Password1!", True, True)
    signup(client, "charrison16082002@gmail.com", "Password1!", "Password1!", True, True)
    signup(client, "smartnotes_uol+test@protonmail.com", "Password1!", "Password1!", True, True)
    with app.app_context():
        user1 = models.User.query.filter_by(email="smartnotes_uol@protonmail.com").first()
        user2 = models.User.query.filter_by(email="charrison16082002@gmail.com").first()
        user3 = models.User.query.filter_by(email="smartnotes_uol+test@protonmail.com").first()
    verify(client, user1.id)
    verify(client, user2.id)
    verify(client, user3.id)

    # Create A Group with a folder
    login(client, "smartnotes_uol@protonmail.com", "Password1!")
    create_group(client, "Test Group")
    with app.app_context():
        group = models.Group.query.filter_by(title="Test Group", owner=user1.id).first()
    create_folder(client, group.id, "Test Folder")
    with app.app_context():
        folder = models.Folder.query.filter_by(title="Test Folder", group=group.id).first()

    # Member Joins Group
    client.get('/logout')
    login(client, "charrison16082002@gmail.com", "Password1!")
    join_group(client, group.code)
    client.get('/logout')
    login(client, "smartnotes_uol+test@protonmail.com", "Password1!")
    join_group(client, group.code)
    with app.app_context():
        member1 = models.Member.query.filter_by(user=user2.id, group=group.id).first()
        member2 = models.Member.query.filter_by(user=user3.id, group=group.id).first()

    # Add a URL
    add_url(client, folder.id, "https://www.google.com", "Google")
    with app.app_context():
        resource = models.Resource.query.filter_by(title="Google", folder=folder.id).first()
    
    # Create Review
    client.get('/logout')
    login(client, "charrison16082002@gmail.com", "Password1!")
    review_resource(client, resource.id, 5, "Test Review")
    with app.app_context():
        review = models.Review.query.filter_by(resource=resource.id, creator=user2.id).first()

    # Test Delete Review
    client.get('/logout')
    login(client, "smartnotes_uol@protonmail.com", "Password1!")
    res1 = delete_review(client, "")
    assert b"Invalid form!" in res1.data

    res2 = delete_review(client, 9999)
    assert b"Review not found!" in res2.data

    client.get("/logout")
    login(client, "smartnotes_uol+test@protonmail.com", "Password1!")
    res3 = delete_review(client, review.id)
    assert b"You cannot delete this review!" in res3.data

    client.get("/logout")
    login(client, "smartnotes_uol@protonmail.com", "Password1!")
    res4 = delete_review(client, review.id)
    assert b"Review deleted!" in res4.data
    with app.app_context():
        review = models.Review.query.filter_by(resource=resource.id, creator=user2.id).first()
    assert review is None

    # Tear Down
    with app.app_context():
        st = models.SearchTree.query.filter_by(folder=folder.id).first()
        db.session.delete(st)
        db.session.delete(folder)
        db.session.delete(group)
        db.session.delete(member1)
        db.session.delete(member2)
        db.session.delete(user1)
        db.session.delete(user2)
        db.session.delete(user3)
        db.session.delete(resource)
        db.session.commit()

"""
Test Report Resource Variations:
1. No Resource ID
2. Invalid Resource ID
3. Invalid, Resource's Group Owner
4. Invalid, Resources Creator
5. Everything Valid, Not Reported Before
6. Everything Valid, Reported Before
7. Everything Valid, Not Reported Before, Max Reports Exceeded
"""
def test_report_resource(app, client):

    def report_resource(client, resource_id):
        return client.post('/resource/report',
                            data=dict(resource_id=resource_id),
                            follow_redirects=True)
    
    # Create 4 user (1 admin, 3 members)
    signup(client, "smartnotes_uol@protonmail.com", "Password1!", "Password1!", True, True)
    signup(client, "charrison16082002@gmail.com", "Password1!", "Password1!", True, True)
    signup(client, "smartnotes_uol+test@protonmail.com", "Password1!", "Password1!", True, True)
    signup(client, "charrison16082002+test@gmail.com", "Password1!", "Password1!", True, True)
    with app.app_context():
        user = models.User.query.filter_by(email="smartnotes_uol@protonmail.com").first()
        user2 = models.User.query.filter_by(email="charrison16082002@gmail.com").first()
        user3 = models.User.query.filter_by(email="smartnotes_uol+test@protonmail.com").first()
        user4 = models.User.query.filter_by(email="charrison16082002+test@gmail.com").first()
    verify(client, user.id)
    verify(client, user2.id)
    verify(client, user3.id)
    verify(client, user4.id)

    # Create A Group with a folder
    login(client, "smartnotes_uol@protonmail.com", "Password1!")
    create_group(client, "Test Group")
    with app.app_context():
        group = models.Group.query.filter_by(title="Test Group", owner=user.id).first()
    create_folder(client, group.id, "Test Folder")
    with app.app_context():
        folder = models.Folder.query.filter_by(title="Test Folder", group=group.id).first()
    
    # All Other Users Join Group
    client.get('/logout')
    login(client, "charrison16082002@gmail.com", "Password1!")
    join_group(client, group.code)
    client.get('/logout')
    login(client, "smartnotes_uol+test@protonmail.com", "Password1!")
    join_group(client, group.code)
    client.get('/logout')
    login(client, "charrison16082002+test@gmail.com", "Password1!")
    join_group(client, group.code)

    with app.app_context():
        member = models.Member.query.filter_by(user=user2.id, group=group.id).first()
        member2 = models.Member.query.filter_by(user=user3.id, group=group.id).first()
        member3 = models.Member.query.filter_by(user=user4.id, group=group.id).first()

    # Create A Resource
    client.post('/add_url', data=dict(url="https://www.google.com", title="Google"), query_string=dict(folder=folder.id), follow_redirects=True)
    with app.app_context():
        resource = models.Resource.query.filter_by(title="Google", folder=folder.id).first()
    
    client.get("/logout")
    login(client, "charrison16082002@gmail.com", "Password1!")

    res1 = report_resource(client, "")
    assert b"Invalid request" in res1.data

    res2 = report_resource(client, 0)
    assert b"Invalid request" in res2.data

    client.get('/logout')
    login(client, "smartnotes_uol@protonmail.com", "Password1!")
    res3 = report_resource(client, resource.id)
    assert b"You cannot report a resource you can delete." in res3.data

    client.get('/logout')
    login(client, "charrison16082002+test@gmail.com", "Password1!")
    res4 = report_resource(client, resource.id)
    assert b"You cannot report a resource you can delete." in res4.data

    client.get('/logout')
    login(client, "charrison16082002@gmail.com", "Password1!")
    res5 = report_resource(client, resource.id)
    assert b"Resource reported" in res5.data
    with app.app_context():
        reports = models.Report.query.filter_by(item=resource.id, type="resource", user=user2.id).all()
    assert len(reports) == 1

    res6 = report_resource(client, resource.id)
    assert b"You have already reported this resource" in res6.data
    with app.app_context():
        reports = models.Report.query.filter_by(item=resource.id, type="resource", user=user2.id).all()
    assert len(reports) == 1

    client.get('/logout')
    login(client, "smartnotes_uol+test@protonmail.com", "Password1!")
    res7 = report_resource(client, resource.id)
    assert b"Resource reported" in res7.data
    with app.app_context():
        reports = models.Report.query.filter_by(item=resource.id, type="resource").all()
        resource = models.Resource.query.filter_by(id=resource.id).first()
    assert len(reports) == 0
    assert resource is None

    # Tear Down: Remove any modifications
    with app.app_context():
        db.session.delete(user)
        db.session.delete(user2)
        db.session.delete(user3)
        db.session.delete(user4)
        db.session.delete(member)
        db.session.delete(member2)
        db.session.delete(member3)
        db.session.delete(group)
        st = models.SearchTree.query.filter_by(folder=folder.id).first()
        db.session.delete(st) 
        db.session.delete(folder)
        db.session.commit()

"""
Test Report Review Variations:
1. No Review ID
2. Invalid Review ID
3. Invalid, Review's Creator
4. Invalid, Review's Group Owner
5. Everything Valid, Not Reported Before
6. Everything Valid, Reported Before
7. Everything Valid, Not Reported Before, Max Reports Exceeded
"""
def test_report_review(client, app):
    def report_review(client, review_id):
        return client.post('/review/report',
                            data=dict(review_id=review_id),
                            follow_redirects=True)
    
    # Create 4 user (1 admin, 3 members)
    # User 1 creates the resource
    # User 2 creates the review
    signup(client, "smartnotes_uol@protonmail.com", "Password1!", "Password1!", True, True)
    signup(client, "charrison16082002@gmail.com", "Password1!", "Password1!", True, True)
    signup(client, "smartnotes_uol+test@protonmail.com", "Password1!", "Password1!", True, True)
    signup(client, "charrison16082002+test@gmail.com", "Password1!", "Password1!", True, True)
    with app.app_context():
        user = models.User.query.filter_by(email="smartnotes_uol@protonmail.com").first()
        user2 = models.User.query.filter_by(email="charrison16082002@gmail.com").first()
        user3 = models.User.query.filter_by(email="smartnotes_uol+test@protonmail.com").first()
        user4 = models.User.query.filter_by(email="charrison16082002+test@gmail.com").first()
    verify(client, user.id)
    verify(client, user2.id)
    verify(client, user3.id)
    verify(client, user4.id)

    # Create A Group with a folder
    login(client, "smartnotes_uol@protonmail.com", "Password1!")
    create_group(client, "Test Group")
    with app.app_context():
        group = models.Group.query.filter_by(title="Test Group", owner=user.id).first()
    create_folder(client, group.id, "Test Folder")
    with app.app_context():
        folder = models.Folder.query.filter_by(title="Test Folder", group=group.id).first()
    
    # All Other Users Join Group
    client.get('/logout')
    login(client, "charrison16082002@gmail.com", "Password1!")
    join_group(client, group.code)
    client.get('/logout')
    login(client, "smartnotes_uol+test@protonmail.com", "Password1!")
    join_group(client, group.code)
    client.get('/logout')
    login(client, "charrison16082002+test@gmail.com", "Password1!")
    join_group(client, group.code)

    with app.app_context():
        member = models.Member.query.filter_by(user=user2.id, group=group.id).first()
        member2 = models.Member.query.filter_by(user=user3.id, group=group.id).first()
        member3 = models.Member.query.filter_by(user=user4.id, group=group.id).first()

    # Create A Resource (As Admin)
    client.get("/logout")
    login(client, "smartnotes_uol@protonmail.com", "Password1!")
    client.post('/add_url', data=dict(url="https://www.google.com", title="Google"), query_string=dict(folder=folder.id), follow_redirects=True)
    with app.app_context():
        resource = models.Resource.query.filter_by(title="Google", folder=folder.id).first()
    
    # Create A Review (As User 2)
    client.get("/logout")
    login(client, "charrison16082002@gmail.com", "Password1!")
    client.post('/review', data=dict(resource_id=resource.id, rating=5, review="This is a test review"), follow_redirects=True)
    with app.app_context():
        review = models.Review.query.filter_by(resource=resource.id, creator=user2.id).first()

    res1 = report_review(client, "")
    assert b"Invalid form!" in res1.data

    res2 = report_review(client, 0)
    assert b"Review not found!" in res2.data

    res3 = report_review(client, review.id)
    assert b"You cannot report reviews you have the ability to delete" in res3.data

    client.get('/logout')
    login(client, "smartnotes_uol@protonmail.com", "Password1!")
    res4 = report_review(client, review.id)
    assert b"You cannot report reviews you have the ability to delete" in res4.data

    client.get('/logout')
    login(client, "charrison16082002+test@gmail.com", "Password1!")
    res5 = report_review(client, review.id)
    assert b"Review reported" in res5.data
    with app.app_context():
        reports = models.Report.query.filter_by(item=review.id, type="review", user=user4.id).all()
    assert len(reports) == 1

    res6 = report_review(client, review.id)
    assert b"You have already reported this review" in res6.data
    with app.app_context():
        reports = models.Report.query.filter_by(item=review.id, type="review", user=user4.id).all()
    assert len(reports) == 1

    client.get('/logout')
    login(client, "smartnotes_uol+test@protonmail.com", "Password1!")
    res7 = report_review(client, review.id)
    assert b"Review reported" in res7.data
    with app.app_context():
        reports = models.Report.query.filter_by(item=review.id, type="review").all()
        review = models.Review.query.filter_by(id=review.id).first()
    assert len(reports) == 0
    assert review is None

    # Tear Down: Remove any modifications
    with app.app_context():
        db.session.delete(user)
        db.session.delete(user2)
        db.session.delete(user3)
        db.session.delete(user4)
        db.session.delete(member)
        db.session.delete(member2)
        db.session.delete(member3)
        db.session.delete(group)
        st = models.SearchTree.query.filter_by(folder=folder.id).first()
        db.session.delete(st)
        db.session.delete(folder)
        db.session.delete(resource)
        db.session.commit()