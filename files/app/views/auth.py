from app import app
from flask import render_template, request, flash, redirect, url_for, Markup

@app.route('/', methods=['GET', 'POST'])
def index():
    return "Hello World!"