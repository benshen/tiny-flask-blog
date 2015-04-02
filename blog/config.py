#!/usr/bin/env python

class Config(object):
    DEBUG = False
    TESTING = False
    PER_PAGE = 10


class DevConfig(Config):
    DEBUG = True
    SECRET_KEY = 'a;lskdjfalzlkdjals23isdf'
    USERNAME = 'xiaoben'
    PASSWORD = 'xiaoben'
    PER_PAGE = 5


class TestingConfig(Config):
    TESTING = True


class ProductionConfig(Config):
    pass
