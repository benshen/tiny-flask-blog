#!/usr/bin/env python

from flask import Flask
import logging


app = Flask(__name__)
app.config.from_object('blog.config.DevConfig')

# setup logger
logger = logging.getLogger('xiaoben')
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
logger.addHandler(ch)

# import releated modules
from models import create_tables
from helper import load_settings, generate_csrf_token

# setup CSRF Protection
app.jinja_env.globals['csrf_token'] = generate_csrf_token

# setup others
load_settings()

from blog import views
