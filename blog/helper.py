#!/usr/bin/env python

from blog import app
from flask import session
from models import Profile
import string
import random


def load_settings():
    try:
        settings = Profile.select()[0]
        app.jinja_env.globals['blog_title'] = settings.blog_title
        app.jinja_env.globals['blog_nickname'] = settings.blog_nickname
        app.jinja_env.globals['blog_description'] = settings.blog_description
        app.jinja_env.globals['about_me'] = settings.about_me_html
        app.config.update(PER_PAGE=settings.per_page)
        app.config.update(INSTALL=False)
    except:
        app.config.update(INSTALL=True)


def random_string():
    chars = string.ascii_uppercase + string.digits + string.ascii_lowercase
    return ''.join(random.choice(chars) for i in range(24))


def generate_csrf_token():
    if '_csrf_token' not in session:
        session['_csrf_token'] = random_string()
    return session['_csrf_token']
