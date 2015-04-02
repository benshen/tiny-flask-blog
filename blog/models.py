#!/usr/bin/env python

import datetime
import os
import re
from peewee import *
from markdown import markdown
from blog import app
from werkzeug.security import generate_password_hash, check_password_hash
import pinyin


db = SqliteDatabase('blog.db')


class BaseModel(Model):

    class Meta:
        database = db


class User(BaseModel):
    username = CharField(unique=True)
    password = CharField()
    email = CharField()
    nickname = CharField()
    role = IntegerField(default=1)
    join_date = DateTimeField(default=datetime.datetime.now())

    class Meta:
        order_by = ('username',)

    def __str__(self):
        return self.username

    def is_authenticated(self):
        return True

    def is_active(self):
        return True

    def is_anonymous(self):
        return False

    def get_id(self):
        try:
            return unicode(self.id)  # python 2
        except NameError:
            return str(self.id)  # python 3

    def save(self, *args, **kwargs):
        self.password = generate_password_hash(self.password)
        return super(User, self).save(*args, **kwargs)

    def check_password(self, password):
        return check_password_hash(self.password, password)


class Category(BaseModel):
    name = CharField(unique=True)

    class Meta:
        order_by = ('name',)

    def __str__(self):
        return self.name

    @property
    def articles(self):
        return self.articles

    @property
    def article_count(self):
        return self.articles.count()


class Article(BaseModel):
    title = CharField()
    slug = CharField(unique=True)
    content = TextField()
    is_published = BooleanField(default=True, index=True)
    post_date = DateTimeField(default=datetime.datetime.now(), index=True)

    author = ForeignKeyField(User)
    category = ForeignKeyField(Category, related_name="articles")

    class Meta:
        order_by = ('-post_date',)

    @property
    def tags(self):
        return Tag.select().join(ArticleTagThrough).where(ArticleTagThrough.article == self.id)

    @property
    def html(self):
        "Convert markdown content to html"
        return markdown(self.content, ['markdown.extensions.extra'])

    @property
    def abstract(self):
        # is there a tag: <!-- more --> or <!--more--> ?
        index = self.content.find('<!-- more -->')
        if index != -1:
            return markdown(self.content[:index], ['markdown.extensions.extra'])

        index = self.content.find('<!--more-->')
        if index != -1:
            return markdown(self.content[:index], ['markdown.extensions.extra'])

        return None

    def save(self, *args, **kwargs):
        # Generate a URL-friendly representation of the entry's title.
        if not self.slug:
            self.slug = re.sub('[^\w]+', '-', self.title.lower()).strip('-')

        if len(self.slug.split()) > 0:
            self.slug = re.sub('[^\w]+', '-', self.slug.lower()).strip('-')
        else:
            self.slug = pinyin.get(self.title)  # deal with chinese characters
            self.slug = re.sub('[^\w]+', '-', self.slug.lower()).strip('-')

        # deal with slug conflict
        slug_suffix = 2
        while True:
            try:
                self.get(Article.slug == self.slug)
            except:
                break
            self.slug += "-%d" % slug_suffix
            slug_suffix += 1

        ret = super(Article, self).save(*args, **kwargs)
        return ret

    @classmethod
    def public(cls):
        return Article.select().where(Article.is_published == True)

    @classmethod
    def drafts(cls):
        return Article.select().where(Article.is_published == False)


class Tag(BaseModel):
    name = CharField(unique=True)

    class Meta:
        order_by = ('name',)

    def __str__(self):
        return self.name

    @property
    def articles(self):
        return Article.select().join(ArticleTagThrough).where(ArticleTagThrough.tag == self.id)

    @property
    def article_count(self):
        return self.articles.count()


class ArticleTagThrough(BaseModel):
    article = ForeignKeyField(Article)
    tag = ForeignKeyField(Tag)

    class Meta:
        indexes = (
            (('article', 'tag'), True),
        )


class Comment(BaseModel):
    nickname = CharField()
    email = CharField()
    website = CharField(null=True)
    content = TextField()
    post_date = DateTimeField(default=datetime.datetime.now())
    parent = ForeignKeyField('self', related_name='children', null=True)
    article = ForeignKeyField(Article, related_name='comments')


class Profile(BaseModel):
    blog_title = CharField()
    blog_description = CharField()
    blog_nickname = CharField()
    about_me = TextField()
    per_page = IntegerField()

    @property
    def about_me_html(self):
        "Convert markdown content to html"
        return markdown(self.about_me, ['markdown.extensions.extra'])


def create_tables():
    db.connect()
    db.create_tables(
        [User, Article, Tag, Category, ArticleTagThrough, Comment, Profile], safe=True)
