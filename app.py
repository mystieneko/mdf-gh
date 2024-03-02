from dotenv import load_dotenv
from flask import Flask, render_template, request, url_for, flash, redirect, session
from flask_caching import Cache
from markupsafe import Markup
from werkzeug.exceptions import abort
from functools import wraps
from bleach.sanitizer import Cleaner
from feedgen.feed import FeedGenerator
from pathlib import Path
import markupsafe
import mysql.connector
import mistune
import os
import re
import bcrypt
import time
import pytz
import json

"""
this is needed to ensure that load_dotenv() loads .env file from the right
path, because load_dotenv() without arguments doesn't work with WSGI
"""
env_path = Path.cwd() / ".env"
load_dotenv(dotenv_path=env_path)

db_user = os.environ.get("DB_USER")
db_pass = os.environ.get("DB_PASS")
db_name = os.environ.get("DB_NAME")
db_host = os.environ.get("DB_HOST")

VERSION = '2024.0302.1'
VERSION_MOD_LEFT = ''
VERSION_MOD_RIGHT = '+dev'
MAIN_CONFIG_FILE = 'config/main.json'
GISCUS_CONFIG_FILE = 'config/giscus.json'

def loadJSON(config_name):
    with open(config_name, 'r') as file:
        return json.load(file)

def saveJSON(config_dict, config_name):
    with open(config_name, 'w') as file:
        json.dump(config_dict, file, indent=4)

config = loadJSON(MAIN_CONFIG_FILE)
giscusConfig = loadJSON(GISCUS_CONFIG_FILE)
config['CACHE_TIMEOUT'] = int(config['CACHE_TIMEOUT'])

def connect():
    conn = mysql.connector.connect(
        host=db_host,
        user=db_user,
        password=db_pass,
        database=db_name,
        pool_name="dbpool",
        pool_size=32,
        autocommit=True
    )
    return conn

def getPost(slug):
    conn = connect()
    cursor = conn.cursor()

    query = '''SELECT p.id, p.title, p.slug, p.content,
               p.created, p.tags, DATE_FORMAT(p.created, %s) AS created
               FROM posts p WHERE p.slug = %s'''

    cursor.execute(query, (config['DATE_FORMAT'], slug,))
    row = cursor.fetchone()

    if row is None:
        return None

    post = {
        'id': row[0],
        'title': row[1],
        'slug': row[2],
        'content': row[3],
        'created': row[4],
        'tags': row[5].split(','),
        'created_formatted': row[6]
    }

    cursor.close()
    conn.close()

    return post

def getAllPosts():
    conn = connect()
    cursor = conn.cursor()
    
    query = '''SELECT p.id, p.title, p.slug, p.content, 
                           p.created, p.tags,
                           DATE_FORMAT(p.created, %s) AS created_date  
                      FROM posts p
                      ORDER BY p.created DESC'''
               
    cursor.execute(query, (config['DATE_FORMAT'],))
    
    posts = []
    
    for row in cursor:
        post = {
           "id": row[0],
           "title": row[1],
           "slug": row[2],
           "content": row[3],
           "created": row[4],
           "tags": row[5].split(','),
           "created_formatted": row[6]
        }
        posts.append(post)
        
    cursor.close()
    conn.close()
    
    return posts

def getPosts(filters=None):
    posts = getAllPosts()

    if filters and 'tag' in filters:
        tagged = [post for post in posts if filters['tag'] in post['tags']]
        return tagged
    else:
        return posts

def getPage(slug):

    conn = connect()
    cursor = conn.cursor()

    query = '''SELECT pg.id, pg.title, pg.slug, pg.content
               FROM pages pg WHERE pg.slug = %s'''

    cursor.execute(query, (slug,))
    row = cursor.fetchone()

    if row is None:  
        return None

    page = {
        'id': row[0],
        'title': row[1],
        'slug': row[2],
        'content': row[3],
    }

    cursor.close()
    conn.close()

    return page

def getTheme():
    return session.get('theme') or config['THEME']

def generateSlug(title):
    slug = re.sub(r'[^\w\s-]', '', title)
    slug = re.sub(r'\s+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    slug = re.sub(r'/+', '-', slug)
    slug = slug.lower()
    return slug

def cached(route):
    if config['CACHE_ENABLED'] == "True":
        return cache.cached(timeout=config['CACHE_TIMEOUT'])(route)
    return route

cache_config = {
    "DEBUG": True,
    "CACHE_TYPE": "SimpleCache",
    "CACHE_DEFAULT_TIMEOUT": 300
}

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get("APP_SECRET")
app.config.from_mapping(cache_config)
app.config.from_mapping(config)
app.config["AUTOESCAPE"] = True
cache = Cache(app)

@app.before_request
def before_request():
    if not session.get('theme'):
        session['theme'] = 'dark.css'

themes = {}

themes_dir = './static/css/themes/'

for filename in os.listdir(themes_dir):
    if filename.endswith(".css"):
        theme_file_path = os.path.join(themes_dir, filename)
        with open(theme_file_path, 'r') as css_file:
            css_content = css_file.read()
            theme_match = re.search(r'/\* @theme\s+(.*?)\s*\*/', css_content)
            theme_name = theme_match.group(1) if theme_match else 'Unknown Theme'
            themes[theme_name] = filename

@app.errorhandler(404)
def notfound(error):
    return render_template('errorpages/404.html'), 404

@app.errorhandler(403)
def forbidden(error):
    return render_template('errorpages/403.html'), 403

@app.errorhandler(500)
def internalservererror(error):
    return render_template('errorpages/500.html'), 500

@app.context_processor
def inject_translations():
    lang = session.get('lang') or config['DEFAULT_LANG_SHORT'] or 'en'
    translations = loadJSON(f"translations/strings_{lang}.json")
    return dict(translations=translations, lang=lang)

@app.context_processor
def inject_version():
    return dict(version=VERSION, version_mod_left=VERSION_MOD_LEFT, version_mod_right=VERSION_MOD_RIGHT)

@app.context_processor
def inject_theme():
    return dict(theme_name=session.get('theme'), themes=themes)

@app.context_processor
def inject_tohtml():
    return dict(to_html=mistune.html)

@app.route('/change_lang/', methods=['POST'])
def changeLang():
    lang = request.form['language']
    session['lang'] = lang
    return redirect(request.referrer)

app.context_processor(inject_version)

@app.route('/admin/', methods=['GET', 'POST'])
def admin():
    if not (session.get('user') and session['user_role'] == 'admin'):
        abort(403)
    if request.method == 'POST':
        # Save changes
        config = loadJSON(MAIN_CONFIG_FILE)
        for key, value in request.form.items():
            # Update the config dictionary with the new value
            config[key] = value
        saveJSON(config, MAIN_CONFIG_FILE)
        app.config.update(config)
        flash('Changes saved!', 'success')
        return redirect(url_for('admin'))
    else:
        # Render the admin page with editable inputs
        config_vars = loadJSON(MAIN_CONFIG_FILE)
        return render_template('admin/index.html', config_vars=config_vars)

@app.route('/admin/currentconfig/')
def admin_currentconf():
    if not session['user_role'] == 'admin':
        abort(403)

    config_vars = loadJSON(MAIN_CONFIG_FILE)

    return render_template('admin/currentconf.html', config=config_vars)

@app.route('/account/', methods=['GET', 'POST'])
def accountSettings():
    if not session.get('user'):
        return redirect(url_for('login'))
    return redirect(url_for('accountSecurity'))

@app.route('/change_theme/', methods=['POST'])
def changeTheme():
    if request.method == "POST":
        theme = request.form['theme']
        print(theme)
        session['theme'] = theme
        return redirect(request.referrer)

@app.route('/account/security/', methods=['GET'])
def accountSecurity():
    if not session.get('user'):
        return redirect(url_for('login'))
    return render_template('account/security.html')

@app.route('/account/authentication/', methods=['GET'])
def accountAuth():
    if not session.get('user'):
        return redirect(url_for('login'))

    return render_template('account/auth.html')

@app.route('/account/change_password/', methods=['POST'])
def changePassword():
    if not session.get('user'):
        return redirect(url_for('index'))
    if request.method == 'POST':
        current_password = request.form['currentpass']
        new_password = request.form['newpass']
        confirm_password = request.form['newpassconfirm']
        
        conn = connect()
        cursor = conn.cursor()
        cursor.execute('''SELECT * FROM users  
            WHERE name=%s''', (session['user'],))
        user = cursor.fetchone()
            
        if not bcrypt.checkpw(current_password.encode('utf-8'), user[3].encode('utf-8')):
            flash('Current password is incorrect')
            return render_template('account/base.html')
            
        if new_password != confirm_password:
            flash('New passwords do not match')
            return render_template('account/base.html')
            
        new_hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
        
        query = """UPDATE users
                SET password=%s
                WHERE name=%s"""

        cursor.execute(query, (new_hashed_password, session['user']))
        conn.commit()
        cursor.close()
        conn.close()
        flash('Password changed successfully!')
        
        session.pop('user', None)
        return redirect(url_for('login'))

@app.route('/account/change_username/', methods=['POST'])
def changeUsername():
    if not session.get('user'):
        return redirect(url_for('index'))
    if request.method == 'POST':
        current_password = request.form['currentpass_n']
        new_username = request.form['newusername']

        conn = connect()
        cursor = conn.cursor()

        # validate current password
        cursor.execute('''SELECT * FROM users
            WHERE name=%s''', (session['user'],))
        user = cursor.fetchone()
        
        if not bcrypt.checkpw(current_password.encode('utf-8'), user[3].encode('utf-8')):
            flash('Current password is incorrect')
            return render_template('account/base.html')

        # check if new username is available
        cursor.execute('''SELECT * FROM users WHERE name=%s''', (new_username,))
        username_exists = cursor.fetchone()

        if username_exists:
            flash('This username is already taken')
            return render_template('account/base.html')

        # update username
        update_sql = """UPDATE users SET name=%s WHERE name=%s"""
        cursor.execute(update_sql, (new_username, session['user']))
        
        conn.commit()
        cursor.close()
        conn.close()

        flash('Username changed successfully!')
        session.pop('user', None)
        return redirect(url_for('login'))

@app.route('/account/delete_account/', methods=['POST'])
def deleteAccount():
    if not session.get('user'):
        return redirect(url_for('index'))
    if request.method == 'POST':
        current_password = request.form['currentpass_d'] 

        conn = connect()
        cursor = conn.cursor()

        # validate current password
        cursor.execute('''SELECT * FROM users
            WHERE name=%s''', (session['user'],))  
        user = cursor.fetchone()
        
        if not bcrypt.checkpw(current_password.encode('utf-8'), user[3].encode('utf-8')):
            flash('Password is incorrect')
            return render_template('account/base.html')

        # delete account
        delete_sql = """DELETE FROM users WHERE name=%s"""
        cursor.execute(delete_sql, [session['user']])
        
        conn.commit()
        cursor.close()
        conn.close()

        session.pop('user', None)
        flash('Your account was successfully deleted.')
        return redirect(url_for('login'))

user_requests = {}

@app.route('/register/', methods=['GET', 'POST'])
def register():
    if config["REGISTRATIONS_OPENED"] == "True":
        if session.get('user'):
            flash("Why are you trying to register while logged in???")
            return redirect(url_for('index'))

        if request.method == 'POST':
            user_ip = request.remote_addr

            now = time.time()
            if user_ip not in user_requests:
                user_requests[user_ip] = []

            user_requests[user_ip] = [t for t in user_requests[user_ip] if now - t < 86400]

            if len(user_requests[user_ip]) >= int(config['REGISTER_REQUEST_LIMIT']):
                abort(429)

            user_requests[user_ip].append(now)

            name = request.form['name']
            email = request.form['email']
            email_regex = r'^\w+[\+\.\w-]*@([\w-]+\.)*\w+[\w-]*\.([a-z]{2,24}|\d+)$'

            if not re.match(email_regex, email):
                flash('Invalid email')
                return redirect(url_for('register'))

            password = request.form['password']
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
            role = request.form['role']
            if not role:
                flash('Choose a role')
                return redirect(url_for('register'))
            is_approved = 0
            if role == 'user':
                is_approved = 1

            # Create user in database
            conn = connect()
            cursor = conn.cursor()
            query = """INSERT INTO users 
                      (name, email, password, is_approved, role)
                      VALUES (%s, %s, %s, %s, %s)"""

            cursor.execute(query, (name, email, hashed_password, is_approved, role))
            conn.commit()

            cursor.close()
            conn.close()
            
            if config['ADMIN_CONTACT'] != "":
                flash(Markup('"{}" was registered! If you want it approved, <a href="' + config["ADMIN_CONTACT"] + '">contact the admin</a>').format(name))
            else:
                flash(Markup('"{}" was registered! If you want it approved, contact the admin').format(name))

            return redirect(url_for('index'))

        return render_template('account/register.html')
    else:
        flash("Registrations are closed")
        return redirect(url_for('index'))

@app.route('/login/', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':
        # user[3] == password, user[4] == is_approved, user[5] == role
        name = request.form['name']
        password = request.form['password']

        # Check credentials and fetch user
        conn = connect()
        cursor = conn.cursor()
        cursor.execute('''SELECT * FROM users  
                          WHERE name=%s''', (name,))
        user = cursor.fetchone()

        if user and (user[4] == 1 or (user[5] == 'user')) and bcrypt.checkpw(password.encode('utf-8'), user[3].encode('utf-8')):
            # If valid credentials, set user in session
            session['user'] = name
            session['user_approved'] = 1
            session['user_role'] = user[5]
            flash("Successfully logged in!")
            return redirect(url_for('index'))
        elif user and not bcrypt.checkpw(password.encode('utf-8'), user[3].encode('utf-8')):
            flash("Wrong password")
        elif user and user[4] == 0:
            flash("Your account is not yet approved")
            session['user_approved'] = 0
        else:
            flash("Invalid credentials / account doesn't exist")

        cursor.close()
        conn.close()
    return render_template('account/login.html')

@app.route('/logout/')  
def logout():
    if session.get('user'):
        session.pop('user', None)
        session.pop('user_approved', None)
        session.pop('user_role', None)
    return redirect(url_for('index'))

@app.route('/')
def index():
    return render_template('index.html', to_html=mistune.html)

@app.route('/posts/')
@cached
def posts():
    conn = connect()
    cursor = conn.cursor()

    query = '''SELECT p.id, p.title, p.slug, p.content, 
                           p.created,
                           DATE_FORMAT(p.created, %s) AS created_date  
                      FROM posts p
                      ORDER BY p.created DESC'''

    cursor.execute(query, (config['DATE_FORMAT'],))

    posts = []
    for row in cursor:
        post = {
            'id': row[0],
            'title': row[1],
            'slug': row[2],
            'content': row[3],
            'created': row[4],
            'created_formatted': row[5]
        }
        posts.append(post)

    posts_count = len(posts)

    cursor.close()  
    conn.close()

    return render_template('post/list.html', posts=posts, posts_count=posts_count)

@app.route('/search/', methods=['GET'])
def search():
    if config['SEARCH_ENABLED'] == "True":
        search_query = request.args.get('q', '')
        if search_query == '' or search_query == ' ':
            flash("Search query cannot be empty")
            return redirect(request.referrer)

        conn = connect()
        cursor = conn.cursor()

        query = '''SELECT p.id, p.title, p.slug, p.created, DATE_FORMAT(p.created, %s) AS created_date  
                   FROM posts p WHERE title LIKE %s
                   ORDER BY p.created DESC'''
        cursor.execute(query, (config['DATE_FORMAT'], '%' + search_query + '%',))
        posts = []
        for row in cursor:
            post = {
                'id': row[0],
                'title': row[1],
                'slug': row[2],
                'created': row[3],
                'created_formatted': row[4]
            }
            posts.append(post)
        print(posts)

        posts_count = len(posts)

        cursor.close()
        conn.close()

        return render_template('search_results.html', posts=posts, posts_count=posts_count, search_query=search_query)
    else:
        return abort(404)


@app.route('/tag/<tag>/')
@cached
def tag(tag):

    posts = getPosts({'tag': tag})
    posts_count = len(getPosts({'tag': tag}))
  
    return render_template('tag.html', posts=posts, tag=tag, posts_count=posts_count)

@app.route('/pages/')
@cached
def pages():
    if config['SHOW_PAGES'] == "True" or session.get('user'):
        conn = connect()
        cursor = conn.cursor()

        cursor.execute('''SELECT pg.id, pg.title, pg.slug, pg.content
                          FROM pages pg''')

        pages = []
        for row in cursor:
            page = {
                'id': row[0],
                'title': row[1],
                'slug': row[2],
                'content': row[3],
            }
            pages.append(page)

        cursor.close()  
        conn.close()

        return render_template('page/list.html', pages=pages)
    else:
        return redirect(url_for('index'))

@app.template_filter() 
def render_markdown(text):
    plugins = ['strikethrough', 'footnotes', 'table', 'url', 'task_lists', 'abbr', 'mark', 'superscript', 'subscript', 'spoiler']
    allowed_tags = ['p','blockquote','table','tr','td','caption','thead','tbody','th','tfoot','col','colgroup','em','abbr','section','table','strong','input','div','sup','sub','ul','li','h1','h2','h3','h4','h5','h6','ol','a','b','em','strong','i','del','audio','source','br','code','pre','s','img','hr']
    allowed_attrs = {
        'img': ['src', 'alt', 'title'],
        'a': ['href', 'title', 'id'],
        'input': ['type', 'class', 'checked', 'disabled'],
        'abbr': ['title'],
        'sup': ['id', 'class'],
        'li': ['id'],
        'th': ['scope'],
        'blockquote': ['cite']
    }
    md = mistune.create_markdown(escape=True, plugins=plugins)
    html = md(text)
    cleaner = Cleaner(tags=allowed_tags, attributes=allowed_attrs)
    clean_html = cleaner.clean(html)
    return Markup(clean_html)

@app.route('/<slug>/')
@cached
def post(slug):
    post = getPost(slug)
    if post is None:
        return abort(404)
    return render_template('post/view.html', post=post, to_html=mistune.html, giscus=giscusConfig)

@app.route('/p/<slug>/')
@cached
def page(slug):
    page = getPage(slug)
    if page is None:
        return abort(404)
    return render_template('page/view.html', page=page, to_html=mistune.html)

@app.route('/create/')
@cached
def oldCreate():
    return redirect(url_for('create'))

@app.route('/create/page/')
@cached
def oldCreatePage():
    return redirect(url_for('createPage'))

@app.route('/new/', methods=('GET', 'POST'))
def create():
    if session.get('user'):
        if request.method == 'POST':

            title = request.form['title']
            content = request.form['content']
            slug = request.form['slug']

            tags_str = request.form['tags']
            tags_str = tags_str.lower().strip()
            tags = tags_str.split(',')
            tags = [t.strip() for t in tags]

            if slug:
                slug = generateSlug(slug)
            else:
                slug = generateSlug(title)

            slug_exists = getPost(slug) is not None

            counter = 1
            while slug_exists:
                slug = f"{slug}-{counter}"
                slug_exists = getPost(slug) is not None
                counter += 1

            if not title:
                flash('Title is required!')
                return redirect(url_for('create'))
            if len(title) < 5:
                flash('Title is too short!')
                return redirect(url_for('create'))
            if len(title) > int(config["TITLE_LENGTH_LIMIT"]):
                flash('Title is too long! (' + str(len(title)) + " characters out of " + config["TITLE_LENGTH_LIMIT"] + " allowed)")
            if len(slug) > int(config["SLUG_LENGTH_LIMIT"]):
                flash('Slug is too long! (' + str(len(slug)) + " characters out of " + config["SLUG_LENGTH_LIMIT"] + " allowed)")

            else:
                conn = connect()
                cursor = conn.cursor()
                tags_str = ','.join(tags)

                insert_sql = """INSERT INTO posts  
                (title, content, slug, tags)
                VALUES (%s, %s, %s, %s)"""

                cursor.execute(insert_sql, (title, content, slug, tags_str))
                conn.commit()

                cursor.close()
                conn.close()

                flash(Markup('Post created! View it <a href="' + url_for('post', slug=slug) + '">here</a>'))
                return redirect(url_for('index'))
        return render_template('post/create.html')
    else:
        abort(403)

@app.route('/new/page/', methods=('GET', 'POST'))
def createPage():
    if session.get('user'):
        if request.method == 'POST':

            title = request.form['title']
            content = request.form['content']
            slug = request.form['slug']

            if slug:
                slug = generateSlug(slug)
            else:
                slug = generateSlug(title)

            slug_exists = getPage(slug) is not None

            counter = 1
            while slug_exists:
                slug = f"{slug}-{counter}"
                slug_exists = getPost(slug) is not None
                counter += 1

            if not title:
                flash('Title is required!')
                return redirect(url_for('createPage', title=title, content=content))
            if len(title) < 5:
                flash('Title is too short!')
                return redirect(url_for('createPage', title=title, content=content))
            if len(title) > int(config["TITLE_LENGTH_LIMIT"]):
                flash('Title is too long! (' + str(len(title)) + " characters out of " + config["TITLE_LENGTH_LIMIT"] + " allowed)")
            if len(slug) > int(config["SLUG_LENGTH_LIMIT"]):
                flash('Slug is too long! (' + str(len(slug)) + " characters out of " + config["SLUG_LENGTH_LIMIT"] + " allowed)")

            else:
                conn = connect()
                cursor = conn.cursor()

                insert_sql = """INSERT INTO pages  
                (title, content, slug)
                VALUES (%s, %s, %s)"""

                cursor.execute(insert_sql, (title, content, slug))
                conn.commit()

                cursor.close()
                conn.close()

                flash(Markup('Page created! View it <a href="' + url_for('page', slug=slug) + '">here</a>'))
                return redirect(url_for('index'))
        return render_template('page/create.html')
    else:
        abort(403)

@app.route('/p/<slug>/edit/', methods=('GET', 'POST'))
def editPage(slug):
    if session.get('user'):
        page = getPage(slug)
        if page is None:
            return abort(404)
        if request.method == 'POST':
            title = request.form['title']
            content = request.form['content']
            newslug = request.form['slug']

            if newslug:
                newslug = generateSlug(newslug)
            else:
                newslug = generateSlug(title)

            if not title:
                flash('Title is required!')
            if len(title) < 5:
                flash('Title is too short!')
            if len(title) > int(config["TITLE_LENGTH_LIMIT"]):
                flash('Title is too long! (' + str(len(title)) + " characters out of " + config["TITLE_LENGTH_LIMIT"] + " allowed)")
            if len(newslug) > int(config["SLUG_LENGTH_LIMIT"]):
                flash('Slug is too long! (' + str(len(slug)) + " characters out of " + config["SLUG_LENGTH_LIMIT"] + " allowed)")
                
            else:
                conn = connect()
                cursor = conn.cursor()
                
                sql = """UPDATE pages  
                         SET title=%s, content=%s, slug=%s
                         WHERE slug=%s"""
                 
                cursor.execute(sql, (title, content, newslug, slug))  
                conn.commit()
                
                cursor.close()
                conn.close()
                
                return redirect(url_for('page', slug=newslug))
                 
        return render_template('page/edit.html', page=page)
    else:
        abort(403)

@app.route('/<slug>/edit/', methods=('GET', 'POST'))
def edit(slug):
    if session.get('user'):
        post = getPost(slug)
        if post is None:
            return abort(404)
        if request.method == 'POST':
            title = request.form['title']
            content = request.form['content']
            newslug = request.form['slug']
            new_tags_str = request.form['tags']
            new_tags_str = new_tags_str.lower().strip()
            new_tags = [t.strip() for t in new_tags_str.split(',')]

            if newslug:
                newslug = generateSlug(newslug)
            else:
                newslug = generateSlug(title)

            if not title:
                flash('Title is required!')
            if len(title) < 5:
                flash('Title is too short!')
            if len(title) > int(config["TITLE_LENGTH_LIMIT"]):
                flash('Title is too long! (' + str(len(title)) + " characters out of " + config["TITLE_LENGTH_LIMIT"] + " allowed)")
            if len(newslug) > int(config["SLUG_LENGTH_LIMIT"]):
                flash('Slug is too long! (' + str(len(slug)) + " characters out of " + config["SLUG_LENGTH_LIMIT"] + " allowed)")
                
            else:
                conn = connect()
                cursor = conn.cursor()
                
                sql = """UPDATE posts  
                         SET title=%s, content=%s, slug=%s, tags=%s
                         WHERE slug=%s"""
                 
                cursor.execute(sql, (title, content, newslug, ','.join(new_tags), slug))
                conn.commit()
                
                cursor.close()
                conn.close()
                
                return redirect(url_for('post', slug=newslug))
                 
        return render_template('post/edit.html', post=post)
    else:
        abort(403)

@app.route('/p/<slug>/delete/', methods=('POST',))
def deletePage(slug):

    page = getPage(slug)
    if page is None:
        flash('Page not found')
        return redirect(url_for('index'))
    conn = connect()
    cursor = conn.cursor()

    delete_sql = """DELETE FROM pages  
                    WHERE slug = %s"""
    
    cursor.execute(delete_sql, (slug,))
    conn.commit()
    cursor.close()
    conn.close()

    flash('"{}" was successfully deleted!'.format(page['title']))
    
    return redirect(url_for('index'))

@app.route('/<slug>/delete/', methods=('POST',))
def delete(slug):

    post = getPost(slug)
    if post is None:
        flash('Post not found')  
        return redirect(url_for('index'))
    conn = connect()  
    cursor = conn.cursor()

    delete_sql = """DELETE FROM posts  
                    WHERE slug = %s"""
    
    cursor.execute(delete_sql, (slug,))
    conn.commit()
    cursor.close()
    conn.close()

    flash('"{}" was successfully deleted!'.format(post['title']))
    
    return redirect(url_for('index'))

@app.route("/feed/")
def rssFeed():
    fg = FeedGenerator()
    fg.title(config['BLOG_NAME'])
    formatted_desc = render_markdown(config['BLOG_DESC'])
    fg.description(formatted_desc)
    fg.link(href=config['BLOG_DOMAIN'])
    
    posts = getAllPosts() # Custom query to get all posts

    for post in posts:
        fe = fg.add_entry()
        fe.id(str(post['id']))
        fe.title(post['title'])
        formatted_content = render_markdown(post['content'])
        fe.content(formatted_content)
        fe.link(href=url_for("post", slug=post["slug"]))
        with_tz = str(pytz.utc.localize(post["created"]))
        fe.pubDate(with_tz)

    return fg.rss_str(pretty=True)

@app.route('/about/')
def about():
	return render_template('about.html')
