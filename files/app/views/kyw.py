from app import app, db, models, celery
from flask import render_template, request, flash, redirect, url_for
from flask_login import current_user, login_required
from ..forms import *
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
            if len(keywords) == 0:
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