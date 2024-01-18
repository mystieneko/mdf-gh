import sqlite3, mistune, os, re
from dotenv import load_dotenv
from flask import Flask, render_template, request, url_for, flash, redirect
from markupsafe import Markup
import mysql.connector
from werkzeug.exceptions import abort
from functools import wraps
from config import Config
import bcrypt

load_dotenv()

db_user = os.getenv("DB_USER")
db_pass = os.getenv("DB_PASS")
db_name = os.getenv("DB_NAME")
db_host = os.getenv("DB_HOST")

def getDbConnection():
    conn = mysql.connector.connect(
        host=db_host,
        user=db_user,
        password=db_pass,
        database=db_name,
        pool_name="dbpool", pool_size=10,
        autocommit=True
    )
    return conn

def getPost(slug):

    conn = getDbConnection() 
    cursor = conn.cursor()

    query = '''SELECT p.id, p.title, p.slug, p.content,  
               p.created, DATE_FORMAT(p.created, '%m/%d/%Y') AS created  
               FROM posts p WHERE p.slug = %s'''

    cursor.execute(query, (slug,))
    row = cursor.fetchone()

    if row is None:  
        # No post for given slug
        return None

    post = {
        'id': row[0],
        'title': row[1],
        'slug': row[2],
        'content': row[3], 
        'created': row[4],
        'created_formatted': row[5]  
    }

    cursor.close()
    conn.close()
     
    return post

def generateSlug(title):
    slug = re.sub(r'[^\w\s]', '', title)
    slug = re.sub(r'\s+', '-', slug)
    slug = slug.lower()
    
    return slug

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("APP_SECRET")
app.config.from_object(Config)

from flask import session

@app.route('/register', methods=['GET', 'POST'])
def register():
    if app.config["REGISTRATIONS_OPENED"] == 1:
        if session.get('user'):
            flash("Why are you trying to register while logged in???")
            return redirect(url_for('index'))

        if request.method == 'POST':

            name = request.form['name']
            email = request.form['email']
            email_regex = r'^\w+[\+\.\w-]*@([\w-]+\.)*\w+[\w-]*\.([a-z]{2,4}|\d+)$'

            if not re.match(email_regex, email):
                flash('Invalid email')
                return redirect(url_for('register'))

            password = request.form['password']
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
            is_approved = 0

            # Create user in database
            conn = getDbConnection()
            cursor = conn.cursor()
            query = """INSERT INTO users 
                      (name, email, password, is_approved)
                      VALUES (%s, %s, %s, %s)"""

            cursor.execute(query, (name, email, hashed_password, is_approved))
            conn.commit()

            cursor.close()
            conn.close()
            flash(Markup('"{}" was registered! If you want it approved, contact <a href="mailto:' + app.config["ADMIN_EMAIL"] + '">the admin</a>').format(name))
            return redirect(url_for('index'))

        return render_template('register.html')
    else:
        flash("Registrations are closed")
        return redirect(url_for('index'))

@app.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':

        name = request.form['name']
        password = request.form['password']

        # Check credentials and fetch user
        conn = getDbConnection()
        cursor = conn.cursor()
        cursor.execute('''SELECT * FROM users  
                          WHERE name=%s''', (name,))
        user = cursor.fetchone()

        if user and user[4] == 1 and bcrypt.checkpw(password.encode('utf-8'), user[3].encode('utf-8')):
            # If valid credentials, set user in session
            session['user'] = name
            session['user_approved'] = 1
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
    return render_template('login.html')

@app.route('/logout')  
def logout():
    if session.get('user'):
        session.pop('user', None)
    return redirect(url_for('index'))

@app.route('/')
def index():
    return render_template('index.html', to_html=mistune.html)

@app.route('/posts')
def posts():

    conn = getDbConnection()
    cursor = conn.cursor()

    # Query posts
    cursor.execute('''SELECT p.id, p.title, p.slug, p.content, p.created, 
                    DATE_FORMAT(p.created, '%m/%d/%Y') AS created_date  
                    FROM posts p
                    ORDER BY p.created DESC''')
    
    # Fetch and format posts
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

    cursor.close()  
    conn.close()

    return render_template('postList.html', posts=posts)

@app.route('/<slug>')
def post(slug):
    post = getPost(slug)

    if post is None:
         abort(404)
    # this is bad and i could've probably done it better
    giscus_instance = os.getenv('GISCUS_INSTANCE')
    giscus_repo = os.getenv('GISCUS_REPO')
    giscus_repo_id = os.getenv('GISCUS_REPO_ID')
    giscus_category = os.getenv('GISCUS_CATEGORY')
    giscus_category_id = os.getenv('GISCUS_CATEGORY_ID')
    giscus_mapping = os.getenv('GISCUS_MAPPING')
    giscus_strict = os.getenv('GISCUS_STRICT')
    giscus_reactions_enabled = os.getenv('GISCUS_REACTIONS_ENABLED')
    giscus_emit_metadata = os.getenv('GISCUS_EMIT_METADATA')
    giscus_input_position = os.getenv('GISCUS_INPUT_POSITION')
    giscus_theme = os.getenv('GISCUS_THEME')
    giscus_lang = os.getenv('GISCUS_LANG')
    giscus_loading = os.getenv('GISCUS_LOADING')

    return render_template('post.html', post=post, to_html=mistune.html, giscus_instance=giscus_instance, giscus_repo=giscus_repo, giscus_repo_id=giscus_repo_id, giscus_category=giscus_category, giscus_category_id=giscus_category_id, giscus_mapping=giscus_mapping, giscus_strict=giscus_strict, giscus_reactions_enabled=giscus_reactions_enabled, giscus_emit_metadata=giscus_emit_metadata, giscus_input_position=giscus_input_position, giscus_theme=giscus_theme, giscus_lang=giscus_lang, giscus_loading=giscus_loading)

@app.route('/create', methods=('GET', 'POST'))
def create():
    if session.get('user'):
        if request.method == 'POST':

            title = request.form['title']
            content = request.form['content']
            slug = generateSlug(title)

            if len(title) < 5:
                flash('Title is too short!')

            else:
                conn = getDbConnection()
                cursor = conn.cursor()

                insert_sql = """INSERT INTO posts  
                (title, content, slug)  
                VALUES (%s, %s, %s)"""

                cursor.execute(insert_sql, (title, content, slug))
                conn.commit()

                cursor.close()
                conn.close()

                flash(Markup('Post created! View it <a href="' + url_for('post', slug=slug) + '">here</a>'))
                return redirect(url_for('index'))
        return render_template('create.html')
    else:
        abort(403)

@app.route('/<slug>/edit', methods=('GET', 'POST'))
def edit(slug):
    if session.get('user'):
        post = getPost(slug)
        if request.method == 'POST':
            title = request.form['title']
            content = request.form['content']
            
            if len(title) < 5:
                flash('Title is too short!')
                
            else:
                conn = getDbConnection()
                cursor = conn.cursor()
                
                sql = """UPDATE posts  
                         SET title=%s, content=%s
                         WHERE slug=%s"""
                 
                cursor.execute(sql, (title, content, slug))  
                conn.commit()
                
                cursor.close()
                conn.close()
                
                return redirect(url_for('index'))
                 
        return render_template('edit.html', post=post)
    else:
        abort(403)

@app.route('/<slug>/delete', methods=('POST',)) 
def delete(slug):

    post = getPost(slug)
    if post is None:
        flash('Post not found')  
        return redirect(url_for('index'))    
    conn = getDbConnection()  
    cursor = conn.cursor()

    delete_sql = """DELETE FROM posts  
                    WHERE slug = %s"""
    
    cursor.execute(delete_sql, (slug,))
    conn.commit()

    flash('"{}" was successfully deleted!'.format(post['title']))
    
    return redirect(url_for('index'))

@app.route('/about')
def about():
	return render_template('about.html')

@app.route('/roadmap')
def roadmap():
    return render_template('roadmap.html')