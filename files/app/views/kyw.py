from app import app, db, models, celery
from flask import render_template, request, flash, redirect, url_for
from flask_login import current_user, login_required
from ..forms import *
from ..scripts import Node, BinarySearchTree
import logging
import html
import time
import json
import requests
from bs4 import BeautifulSoup
from markdown import markdown
from keybert import KeyBERT
from PyPDF2 import PdfReader
import webvtt
from nltk.stem import PorterStemmer
import string
import html2text

logger = logging.getLogger(__name__)
ps = PorterStemmer()

"""
Generate Keywords Route
POST request only
Requires login
If form validates
    - Get resource
    - If resource does not exist
        - Flash & log error, redirect to index 
    - Get folder
    - If folder does not exist
        - Flash & log error, redirect to index
    - Get group
    - If group does not exist
        - Flash & log error, redirect to index
    - If user is not a member of the group
        - Flash & log error, redirect to resource
    - If keywords already generated
        - Flash & log error, redirect to resource
    - If resource already queued for keyword generation
        - Flash & log error, redirect to resource
    - Create queue entry and add to thread pool 
    - Flash success, redirect to resource
If form does not validate
    - Flash & log error, redirect to resource
"""
@app.route("/generate", methods=["POST"])
@login_required
def generate():
    form = GenerateKeywordsForm()
    if form.validate_on_submit():
        id = int(form.resource_id.data)
        resource = models.Resource.query.filter_by(id=id).first()
        if not resource:
            flash("Resource not found!", "danger")
            logger.warning("User %s tried to generate keywords for a resource that does not exist!", current_user.email)
            return redirect(url_for("index"))
        folder = models.Folder.query.filter_by(id=resource.folder).first()
        if not folder:
            flash("Folder not found!", "danger")
            logger.warning("User %s tried to generate keywords for a resource in a folder that does not exist!", current_user.email)
            return redirect(url_for("index"))
        group = models.Group.query.filter_by(id=folder.group).first()
        if not group:
            flash("Group not found!", "danger")
            logger.warning("User %s tried to generate keywords for a resource in a group that does not exist!", current_user.email)
            return redirect(url_for("index"))
        if current_user.id != group.owner and not models.Member.query.filter_by(user=current_user.id, group=group.id).first():
            flash("You are not a member of this group!", "danger")
            logger.warning("User %s tried to generate keywords for a resource in a group they are not a member of!", current_user.email)
            return redirect(url_for("index"))
        keywords = models.Keywords.query.filter_by(resource=id).first()
        if keywords:
            flash("Keywords already generated!", "danger")
            logger.warning("User %s tried to generate keywords for a resource that already has keywords!", current_user.email)
            return redirect(url_for("resource", id=id))
        queued = models.Queue.query.filter_by(resource=id).first()
        if queued:
            flash("Resource already queued for keyword generation!", "danger")
            logger.warning("User %s tried to generate keywords for a resource that already has keywords queued!", current_user.email)
            return redirect(url_for("resource", id=id))
        entry = models.Queue(resource=id)
        db.session.add(entry)
        db.session.commit()
        wholeQueue = models.Queue.query.all()
        if len(wholeQueue) == 1:
            generator_pipeline.delay()
        flash("Resource queued for keyword generation!", "success")
        logger.info("User %s queued resource %s for keyword generation!", current_user.email, id)
        return redirect(url_for("resource", id=id))
    else:
        flash("Invalid form!", "danger")
        logger.warning("User %s submitted an invalid form!", current_user.email)
        return redirect(url_for("index"))

"""
FOR AJAX USE ONLY
Folder Search Route
GET Request Only
Requires login
Takes folder id and query as parameters
If folder does not exist
    - return message to user
    - log error
If user is not a member of the group
    - return message to user
    - log error
If query is empty
    - return message to user
If query is not empty
    - Get search tree
    - If search tree does not exist
        - return message to user
        - log error
    - If search tree exists
        - Get results using stemmed words
        - If results is empty
            - return message to user
        - If results is not empty
            - return results as rendered page
"""
@app.route("/folder/search", methods=["GET"])
@login_required
def folder_search():
    if not request.args.get("folder_id") or not request.args.get("query"):
        logger.warning("User %s tried to search a folder without providing a folder id or query!", current_user.email)
        return "No resources found", 200
    folder_id = int(request.args.get("folder_id"))
    query = request.args.get("query").strip().lower()
    folder = models.Folder.query.filter_by(id=folder_id).first()
    if not folder:
        logger.warning("User %s tried to search a folder that does not exist!", current_user.email)
        return "No resources found", 200
    group = models.Group.query.filter_by(id=folder.group).first()
    if not group:
        logger.warning("User %s tried to search a folder in a group that does not exist!", current_user.email)
        return "No resources found", 200
    if current_user.id != group.owner and not models.Member.query.filter_by(user=current_user.id, group=group.id).first():
        logger.warning("User %s tried to search a folder in a group they are not a member of!", current_user.email)
        return "No resources found", 200
    if not query:
        logger.info("User %s searched a folder with an empty query!", current_user.email)
        return "No resources found", 200
    SearchTreeDB = models.SearchTree.query.filter_by(folder=folder_id).first()
    if not SearchTreeDB:
        logger.warning("User %s tried to search a folder that does not have a search tree!", current_user.email)
        logger.error("Folder %s does not have a search tree!", folder_id)
        return "No resources found", 200
    tree = BinarySearchTree()
    tree.decode_json(SearchTreeDB.json)
    resources = []
    words = query.split(" ")
    for word in words:
        stem = ps.stem(word)
        node = tree.find(stem)
        if node: # If the word is in the tree
            resources = resources + node.resources
    # Count duplicates in resources and put into a dictionary resource:count
    resource_count = {}
    for resource in resources:
        if resource in resource_count:
            resource_count[resource] += 1
        else:
            resource_count[resource] = 1
    # Sort the dictionary by count, this will put most relevant resources at the start
    sorted_resource_count = sorted(resource_count.items(), key=lambda x: x[1], reverse=True)
    if len(sorted_resource_count) == 0:
        logger.info("User %s searched a folder with a query that returned no results!", current_user.email)
        return "No resources found", 200
    # Convert to a list of resources
    sorted_resources = []
    for resource in sorted_resource_count:
        sorted_resources.append(resource[0])
    resources = models.Resource.query.filter(models.Resource.id.in_(sorted_resources)).all()
    if not resources:
        logger.info('User ' + current_user.email + ' tried to search for resources but none were found')
        return 'No resources found', 200
    dictratings = {}
    dictkeywords = {}
    count = 0
    resources = []
    for r in sorted_resource_count:
        resource = models.Resource.query.filter_by(id=r[0]).first()
        if resource:
            resources.append(resource)
            count += 1
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
    if count == 0:
        logger.info("User %s searched a group with a query that returned no results!", current_user.email)
        return "No resources found", 200
    return render_template('resources.html', resources=resources, ratings=dictratings, keywords=dictkeywords)

"""
FOR AJAX USE ONLY
Group Search Route
GET Request Only
Requires login
Takes group id and query as parameters
If group does not exist
    - return message to user
    - log error
If user is not a member of the group
    - return message to user
    - log error
If query is empty
    - return message to user
If query is not empty
    - For Each Folder
        - Get search tree
        - If search tree does not exist
            - log error
        - If search tree exists
            - Get results using stemmed words
            - If results is empty
                - continue
            - If results is not empty
                - Add results to list of results
    - If list of results is empty
        - return message to user
    - If list of results is not empty
        - return results as rendered page
"""
@app.route("/group/search", methods=["GET"])
@login_required
def group_search():
    if not request.args.get("group_id") or not request.args.get("query"):
        logger.warning("User %s tried to search a group without providing a group id or query!", current_user.email)
        return "No resources found", 200
    group_id = int(request.args.get("group_id"))
    query = request.args.get("query").strip().lower()
    group = models.Group.query.filter_by(id=group_id).first()
    if not group:
        logger.warning("User %s tried to search a group that does not exist!", current_user.email)
        return "No resources found", 200
    if current_user.id != group.owner and not models.Member.query.filter_by(user=current_user.id, group=group.id).first():
        logger.warning("User %s tried to search a group they are not a member of!", current_user.email)
        return "No resources found", 200
    if not query:
        logger.info("User %s searched a group with an empty query!", current_user.email)
        return "No resources found", 200
    folders = models.Folder.query.filter_by(group=group_id).all()
    if not folders:
        logger.info("User %s searched a group with a query that returned no results!", current_user.email)
        return "No resources found", 200
    resources = []
    words = query.split(" ")
    for folder in folders:
        SearchTreeDB = models.SearchTree.query.filter_by(folder=folder.id).first()
        if not SearchTreeDB:
            logger.warning("User %s tried to search a group that does not have a search tree!", current_user.email)
            logger.error("Folder %s does not have a search tree!", folder.id)
            continue
        tree = BinarySearchTree()
        tree.decode_json(SearchTreeDB.json)
        for word in words:
            stem = ps.stem(word)
            node = tree.find(stem)
            if node: # If the word is in the tree
                resources = resources + node.resources
    resource_count = {}
    for resource in resources:
        if resource in resource_count:
            resource_count[resource] += 1
        else:
            resource_count[resource] = 1
    sorted_resource_count = sorted(resource_count.items(), key=lambda x: x[1], reverse=True)
    if len(sorted_resource_count) == 0:
        logger.info("User %s searched a group with a query that returned no results!", current_user.email)
        return "No resources found", 200
    dictratings = {}
    dictkeywords = {}
    count = 0
    resources = []
    for r in sorted_resource_count:
        resource = models.Resource.query.filter_by(id=r[0]).first()
        if resource:
            resources.append(resource)
            count += 1
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
    if count == 0:
        logger.info("User %s searched a group with a query that returned no results!", current_user.email)
        return "No resources found", 200
    logger.info('User ' + current_user.email + ' found resources for query: ' + query)
    return render_template('resources.html', resources=resources, ratings=dictratings, keywords=dictkeywords)

@celery.task
def generator_pipeline():

    # Use keyBERT to extract keywords from text
    def keybert_exec(text):
        try:
            kw_model = KeyBERT(model='all-mpnet-base-v2')
            keywords = kw_model.extract_keywords(
                text, 
                keyphrase_ngram_range=(1, 2), 
                stop_words='english', 
                highlight=False,
                use_maxsum=True,
                use_mmr=True,
                diversity=0.5,
                top_n=10
            )
        except:
            keywords=[]
        return list(dict(keywords).keys())

    # Get the number of hashes in a markdown heading
    def num_hashes(line):
        count = 0
        for letter in line:
            if letter != "#":
                return 0
            else:
                count += 1
        return count

    """
    Get the headings from a markdown file
    1. Split the file into lines
    2. For each line, split it into words
    3. Get the number of hashes in the first word
    4. Remove the hashes from the first word
    5. Remove the carriage return from the last word
    6. Join the words back together
    7. If the number of hashes is greater than 0 and not already in the dictionary, add it
    8. Sort the dictionary such that headers with less hashes come first (less hashes = higher level)
    9. Return the sorted dictionary
    """
    def markdown_headings(resource):
        data = resource.data.split("\n")
        headers = {}
        headers_sorted = []
        for line in data:
            words = line.split(" ")
            hashes = num_hashes(words[0])
            words[-1] = words[-1].replace("\r", "")
            words.pop(0)
            header = " ".join(words)
            if hashes >= 1:
                if header in headers:
                    headers[header] = min(headers[header], hashes)
                else:
                    headers[header] = hashes
        temp = sorted(headers)
        for heading in temp:
            headers_sorted.append(heading)
        return headers_sorted

    """
    Get the notes as plaintext
    1. Convert to html (need to be done for Markdown)
    2. Convert to text from html
    """
    def prepare_notes(resource):
        ht = markdown(html.unescape(resource.data))
        text = ''.join(BeautifulSoup(ht, features="html.parser").findAll(text=True))
        return text

    """
    Get the content from url
    1. If the url is a wikipedia page, get the content from the page
    2. Else do nothing as webscraping is not allowed
    """
    def prepare_url(resource):
        content = ""
        if "wikipedia.org" in resource.data:
            title = resource.data.split("/")[-1]
            try:
                url = "https://en.wikipedia.org/w/api.php?format=json&action=query&prop=extracts&titles="+title+"&redirects=true"
                response = requests.get(url).json()
                if "-1" not in response["query"]["pages"]:
                    h = html2text.HTML2Text()
                    h.ignore_links = True
                    h.ignore_images = True
                    content = h.handle(list(response["query"]["pages"].values())[0]["extract"])
            except:
                logger.info("Could not get content from wikipedia page!!!!!!!! %s", title)
        return content

    """
    Get the content from a pdf
    1. Read the pdf
    2. For each page, extract the text
    3. Merge each page and return
    """
    def prepare_material(resource):
        content = ""
        reader = PdfReader(resource.data)
        for page in reader.pages:
            content += page.extract_text()
        return content

    """
    Get the content from a transcript
    1. If the transcript is a txt file, read the file
    2. Else if the transcript is a vtt file, read the file as captions and merge
    3. Return the content
    """
    def prepare_transcript(resource):
        content = ""
        ext = resource.data.split(".")[-1]
        if ext == "txt":
            with open(resource.data, "r") as f:
                content = f.read()
        elif ext == "vtt":
            for caption in webvtt.read(resource.data):
                content += caption.text + " "
        return content

    """
    1. Get resource and validate exists and queued
    2. Get content
    3. Generate keywords
    4. Save keywords
    5. Remove from queue
    6. Log
    """
    def main(id):
        ps = PorterStemmer()
        id = int(id)
        with app.app_context():
            queued = models.Queue.query.filter_by(resource=id).first()
        if not queued:
            logger.warning("Resource %s is not queued for keyword generation!", id)
            return
        with app.app_context():
            resource = models.Resource.query.filter_by(id=id).first()
        if not resource:
            logger.warning("Resource %s does not exist!", id)
            with app.app_context():
                db.session.delete(queued)
                db.session.commit()
            return

        extra_keywords = []
        content = ""
        if resource.type == "material":
            content = prepare_material(resource)
        elif resource.type == "transcript":
            content = prepare_transcript(resource)
        elif resource.type == "notes":
            extra_keywords = markdown_headings(resource)
            content = prepare_notes(resource)
        elif resource.type == "url":
            content = prepare_url(resource)
        else:
            logger.warning("Resource %d has an invalid type!", id)
            return

        if content == "":
            keywords = ["Extraction unavailable for this resource."]
        else:
            try:
                keywords = extra_keywords + keybert_exec(content)
            except:
                keywords = extra_keywords
                logger.warning("Could not extract keywords for resource %d", id)
            if len(keywords) != 0:        
                tree = BinarySearchTree()
                with app.app_context():
                    SearchTreeDB = models.SearchTree.query.filter_by(folder=resource.folder).first()
                if SearchTreeDB.json != "":
                    tree.decode_json(SearchTreeDB.json)
                stems = []
                for keyword in keywords:
                    words = keyword.split(" ")
                    for w in words:
                        stems.append(ps.stem(w.lower()))
                for stem in stems:
                    node = tree.find(stem)
                    if node is None:
                        tree.insert(stem, [resource.id])
                    else:
                        resources = node.resources
                        if resource.id not in resources:
                            node.resources.append(resource.id)
                SearchTreeDB.json = tree.encode_json()
                with app.app_context():
                    db.session.add(SearchTreeDB)
                    db.session.commit()
            else:
                keywords = ["Extraction failed for this resource."]

        with app.app_context():
            dbEntryKeywords = models.Keywords(resource=id, json=json.dumps(keywords))
            prevKeywords = models.Keywords.query.filter_by(resource=id).all()
            for keywords in prevKeywords:
                db.session.delete(keywords)
            db.session.add(dbEntryKeywords)
            db.session.delete(queued)
            db.session.commit()
        logger.info("Resource %s keywords generated!", id)
        del content
        del keywords
        del extra_keywords
        del resource
        del dbEntryKeywords
        del queued
        del id
        return

    with app.app_context():
        while (item := models.Queue.query.first()) is not None:
            main(item.resource)