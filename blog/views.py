#!/usr/bin/env python

from blog import app, logger
from models import *
from flask import Flask, session, url_for, flash, redirect, render_template, request, abort
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from playhouse.flask_utils import get_object_or_404, object_list
import urllib
from peewee import fn
from helper import random_string, load_settings


@app.before_request
def csrf_protect():
    if request.method == "POST":
        token = session.pop('_csrf_token', None)
        if not token or token != request.form.get('_csrf_token'):
            abort(403)


@app.template_filter()
def timeformat(dt):
    return dt.strftime('%Y/%m/%d %H:%M')


@app.template_filter('clean_querystring')
def clean_querystring(request_args, *keys_to_remove, **new_values):
    # This is from peewee example #
    # We'll use this template filter in the pagination include. This filter
    # will take the current URL and allow us to preserve the arguments in the
    # querystring while replacing any that we need to overwrite. For instance
    # if your URL is /?q=search+query&page=2 and we want to preserve the search
    # term but make a link to page 3, this filter will allow us to do that.
    querystring = dict((key, value) for key, value in request_args.items())
    for key in keys_to_remove:
        querystring.pop(key, None)
    querystring.update(new_values)
    return urllib.urlencode(querystring)


# flask-login
login_manager = LoginManager()
login_manager.init_app(app)


@login_manager.user_loader
def load_user(id):
    try:
        ret = User.get(User.id == int(id))
    except:
        ret = None
    return ret


@login_manager.unauthorized_handler
def need_login():
    logger.debug('need login')
    """
    A user requests the following URL:
       http://www.example.com/myapplication/page.html?x=y

    In this case the values of the above mentioned attributes would be the following:

    path             /page.html
    script_root      /myapplication
    base_url         http://www.example.com/myapplication/page.html
    url              http://www.example.com/myapplication/page.html?x=y
    url_root         http://www.example.com/myapplication/
    """
    next_url = request.path.strip('/')
    return redirect(url_for('login', next=next_url))


@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        try:
            user = User.get(User.username == username)
            if user.check_password(password):
                flash('You were logged in')
                login_user(user)
                return redirect(request.args.get("next") or url_for("admin"))
        except:
            pass

        error = "Invalid username or password or no this user"
        flash(error)
    return render_template('login.html', next=request.args.get("next"), error=error)


@app.route('/logout/')
@login_required
def logout():
    logout_user()
    flash('You were logged out')
    return redirect(url_for('index'))


@app.route('/', methods=['GET'])
@app.route('/index', methods=['GET'])
def index():
    if app.config.get('INSTALL', False):
        return redirect(url_for('install'))

    if current_user.is_authenticated:
        query = Article.select().order_by(Article.post_date.desc())
    else:
        query = Article.public().order_by(Article.post_date.desc())

    if query.count() == 0:
        flash('There is no any article at all, create one please')
        return redirect(url_for('create'))

    # pagination
    return object_list('index.html', query, paginate_by=app.config.get('PER_PAGE'))


@app.route('/blog/<slug>/')
def detail(slug):
    if current_user.is_authenticated:
        query = Article.select()
    else:
        query = Article.public()
    article = get_object_or_404(query, Article.slug == slug)
    comments = article.comments

    qp = query.where(Article.id > article.id).order_by(
        Article.id.asc()).limit(1)
    qn = query.where(Article.id < article.id).order_by(
        Article.id.desc()).limit(1)

    try:
        prev_slug = qp[0].slug
    except:
        prev_slug = None

    try:
        next_slug = qn[0].slug
    except:
        next_slug = None

    return render_template('detail.html', entry=article, comments=comments, prev_slug=prev_slug, next_slug=next_slug)


@app.route('/tags/')
def tags():
    tags = Tag.select()
    return render_template('tags.html', tags=tags)


@app.route('/create/', methods=['GET', 'POST'])
@login_required
def create():
    # get
    if request.method == 'GET':
        categories = Category.select()
        tags = Tag.select()
        return render_template('create.html', categories=categories, tags=tags, entry=None)

    # post
    if request.method == 'POST':
        id = request.form.get('id', None)
        title = request.form.get('title', None)
        slug = request.form.get('slug', None)
        category_id = request.form.get('category', None)
        content = request.form.get('content', None)
        tag_names = request.form.get('tags', None)
        is_published = request.form.get('is_published') or False

        if not title or not content:
            flash("Title and Content can't be empty!")
            return redirect(url_for('create'))

        title = title.strip()
        author = current_user.id
        category = category_id

        tags = []
        if tag_names:
            tag_names = tag_names.strip().split(' ')
            for name in tag_names:
                try:
                    tag = Tag.select().where(
                        fn.Lower(Tag.name) == name.lower())[0]
                except IndexError:
                    tag = Tag.create(name=name)
                #ArticleTagThrough.create(article=article, tag=tag)
                tags.append(tag)

        if id:  # update
            query = Article.update(title=title, category=category, content=content, author=author,
                                   is_published=is_published, slug=slug).where(Article.id == id)
            query.execute()
            article = Article.get(Article.id == id)
        else:   # create
            article = Article.create(title=title, category=category, content=content, author=author,
                                     is_published=is_published, slug=slug)

        # get previous tags
        previous_tags = []
        query = ArticleTagThrough.select().where(
            ArticleTagThrough.article == article.id)
        for article_tag in query:
            previous_tags.append(article_tag.id)

        # update tags
        current_tags = []
        for tag in tags:
            try:
                q = ArticleTagThrough.get(ArticleTagThrough.article == article.id,
                                          ArticleTagThrough.tag == tag.id)
            except:
                # create new tag
                q = ArticleTagThrough.create(article=article, tag=tag)
            current_tags.append(q.id)

        # delete unused tags
        for tag_id in current_tags:
            try:
                previous_tags.remove(tag_id)
            except ValueError:
                pass  # do nothing

        for tag_id in previous_tags:
            qurey = ArticleTagThrough.delete().where(
                ArticleTagThrough.id == tag_id)
            qurey.execute()

        flash('Article created/updated successfully.', 'success')

        if article.is_published:
            return redirect(url_for('detail', slug=article.slug))
        else:
            return redirect(url_for('index'))


@app.route('/blog/edit/<int:id>', methods=['GET'])
@login_required
def edit(id):
    article = get_object_or_404(Article, Article.id == id)
    categories = Category.select()
    tags = Tag.select()

    entry = article
    tag_arry = []
    for tag in article.tags:
        tag_arry.append(tag.name)
    entry_tags = ' '.join(tag_arry)

    return render_template('create.html', categories=categories,
                           tags=tags, entry=entry, entry_tags=entry_tags)


@app.route('/drafts/')
@login_required
def drafts():
    title = "Drafts"
    query = Article.drafts().order_by(Article.post_date.desc())

    if query.count() == 0:
        flash('There is no drafts yet, please create one')
        return redirect(url_for('create'))

    # pagination
    return object_list('lists.html', query, paginate_by=app.config.get('PER_PAGE', 10), title=title)


@app.route('/lists/')
def lists():
    tag = request.args.get('tag')
    cat = request.args.get('cat')

    if cat and not current_user.is_authenticated:
        return redirect(url_for('index'))

    # currently not support tag & cat together, maybe support later
    if tag:
        title = "By tag: %s" % tag
        query = Tag.get(Tag.name == tag).articles
    elif cat:
        title = "By category: %s" % cat
        query = Category.get(Category.name == cat).articles

    return object_list('lists.html', query, paginate_by=app.config.get('PER_PAGE', 10), title=title)


@app.route('/comment/<slug>', methods=['POST'])
def comment(slug):
    nickname = request.form.get('nickname', None)
    email = request.form.get('email', None)
    website = request.form.get('website', None)
    content = request.form.get('content', None)
    article = Article.get(Article.slug == slug)

    if nickname and email and content:
        Comment.create(nickname=nickname, email=email,
                       website=website, content=content, article=article.id)
    else:
        flash("Nickname, email and content can't be empty!")

    return redirect(url_for('detail', slug=slug))


@login_required
@app.route('/admin/')
def admin():
    qurey = Article.select()
    if qurey.count() == 0:
        flash('There is no any article at all, create one please')
        return redirect(url_for('create'))
    return object_list('admin.html', qurey, paginate_by=10)


@login_required
@app.route('/delete/<id>')
def delete(id):
    qurey = Article.delete().where(Article.id == id)
    qurey.execute()

    query = ArticleTagThrough.delete().where(ArticleTagThrough.article == id)
    qurey.execute()

    return redirect(url_for('admin'))


@app.route('/about/')
def about():
    return render_template('about.html')


@login_required
@app.route('/category/')
def category():
    query = Category.select()
    return object_list('category.html', query, paginate_by=app.config.get('PER_PAGE', 10), entry=None)


@login_required
@app.route('/category/add/', methods=['POST'])
def category_add():
    if request.method == 'POST':
        name = request.form.get('name', None)
        if name:
            name = name.strip()
            try:
                Category.get(Category.name == name)
                flash('Error! The category name is existed already')
            except:
                Category.create(name=name)
                flash('Successfully create category: %s' % name)
        return redirect(url_for('category'))


@login_required
@app.route('/category/edit/<int:id>', methods=['GET'])
def category_edit(id):
    try:
        entry = Category.get(Category.id == id)
        flash('Please edit the category name below')
    except:
        entry = None
        flash('Error! The category name: %s is not existed' % name)

    query = Category.select()
    return object_list('category.html', query, paginate_by=app.config.get('PER_PAGE', 10), entry=entry)


@login_required
@app.route('/category/add_or_edit/', methods=['POST'])
def category_add_or_edit():
    if request.method == 'POST':
        name = request.form.get('name', None)
        if name:
            name = name.strip()
            try:
                Category.get(Category.name == name)
                flash('Error! The category name is existed already')
            except:
                id = request.form.get('id', None)
                if id:  # edit
                    query = Category.update(name=name).where(Category.id == id)
                    query.execute()
                    flash('Successfully edited the category name: %s' % name)
                else:  # add
                    Category.create(name=name)
                    flash('Successfully create category: %s' % name)

        return redirect(url_for('category'))


@login_required
@app.route('/category/del/<int:id>')
def category_delete(id):
    # delete the articles which in this category
    query = Article.delete().where(Article.category == id)
    query.execute()
    # delete the cateogry
    qurey = Category.delete().where(Category.id == id)
    qurey.execute()

    return redirect(url_for('category'))


@login_required
@app.route('/settings/', methods=['GET', 'POST'])
def settings():

    if request.method == 'POST':
        blog_title = request.form.get('blog_title')
        blog_nickname = request.form.get('blog_nickname')
        blog_description = request.form.get('blog_description')
        about_me = request.form.get('about_me')
        per_page = request.form.get('per_page')
        id = request.form.get('id')

        if id:  # update
            query = Profile.update(blog_title=blog_title, blog_nickname=blog_nickname,
                                   blog_description=blog_description, about_me=about_me, per_page=per_page)
            query.execute()
            entry = Profile.get(Profile.id == id)

        else:  # create
            entry = Profile.create(blog_title=blog_title, blog_nickname=blog_nickname,
                                   blog_description=blog_description, about_me=about_me, per_page=per_page)

        load_settings()
        flash('Successfully save the settings')
    else:
        try:
            entry = Profile.select()[0]
        except:
            entry = None

    return render_template('settings.html', entry=entry)


@app.route('/install/', methods=['GET', 'POST'])
def install():
    if request.method == 'POST':
        username = request.form.get('username', None)
        password = request.form.get('password', None)
        email = request.form.get('email', None)
        nickname = request.form.get('nickname', None)
        blog_title = request.form.get('blog_title', None)
        blog_nickname = nickname
        blog_description = request.form.get('blog_description', None)
        per_page = request.form.get('per_page', None)
        category = request.form.get('category', None)
        about_me = request.form.get('about_me', None)

        create_tables()

        try:
            User.create(
                username=username, password=password, email=email, nickname=nickname)
        except:
            pass

        try:
            Category.create(name=category)
        except:
            pass

        try:
            Profile.create(blog_title=blog_title, blog_description=blog_description, blog_nickname=blog_nickname,
                           per_page=per_page, about_me=about_me)
        except:
            pass

        app.config.update(INSTALL=False)
        load_settings()
        return redirect(url_for('login'))

    if app.config.get('INSTALL') == False:
        return redirect(url_for('index'))

    return render_template('install.html')
