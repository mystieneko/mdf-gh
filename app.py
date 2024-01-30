from dotenv import load_dotenv
from flask import Flask, render_template, request, url_for, flash, redirect, session
from flask_caching import Cache
from markupsafe import Markup
from werkzeug.exceptions import abort
from functools import wraps
from config import Config, GiscusConfig
import mysql.connector, mistune, os, re, bcrypt, time

load_dotenv()

db_user = os.environ.get("DB_USER")
db_pass = os.environ.get("DB_PASS")
db_name = os.environ.get("DB_NAME")
db_host = os.environ.get("DB_HOST")

def getDbConnection():
    conn = mysql.connector.connect(
        host=db_host,
        user=db_user,
        password=db_pass,
        database=db_name,
        pool_name="dbpool",
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

cache_config = {
    "DEBUG": True,          # some Flask specific configs
    "CACHE_TYPE": "SimpleCache",  # Flask-Caching related configs
    "CACHE_DEFAULT_TIMEOUT": 300
}

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get("APP_SECRET")
app.config.from_object(Config)
app.config.from_mapping(cache_config)
cache = Cache(app)

def cached(route):
    if app.config['CACHE_ENABLED']:
        return cache.cached(timeout=app.config['POSTS_CACHE_TIMEOUT'])(route)
    return route

user_requests = {}

@app.route('/register', methods=['GET', 'POST'])
def register():
    if app.config["REGISTRATIONS_OPENED"]:
        if session.get('user'):
            flash("Why are you trying to register while logged in???")
            return redirect(url_for('index'))

        if request.method == 'POST':
            user_ip = request.remote_addr

            now = time.time()
            if user_ip not in user_requests:
                user_requests[user_ip] = []

            user_requests[user_ip] = [t for t in user_requests[user_ip] if now - t < 86400]

            if len(user_requests[user_ip]) >= app.config['REGISTER_REQUEST_LIMIT']:
                abort(429)

            user_requests[user_ip].append(now)

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
            flash(Markup('"{}" was registered! If you want it approved, <a href="' + app.config["ADMIN_CONTACT"] + '">contact the admin</a>').format(name))
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
@cached
def posts():
    conn = getDbConnection()
    cursor = conn.cursor()

    cursor.execute('''SELECT p.id, p.title, p.slug, p.content, p.created, 
        DATE_FORMAT(p.created, '%m/%d/%Y') AS created_date  
        FROM posts p
        ORDER BY p.created DESC''')

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
@cached
def post(slug):
    post = getPost(slug)
    if post is None:
        abort(404)

    print(GiscusConfig)
    return render_template('post.html', post=post, to_html=mistune.html, giscus=GiscusConfig)

@app.route('/create', methods=('GET', 'POST'))
def create():
    if session.get('user'):
        if request.method == 'POST':

            title = request.form['title']
            content = request.form['content']
            slug = generateSlug(title)

            if len(title) < 5:
                flash('Title is too short!')
            if len(title) > 150:
                flash('Title is too long! (' + str(len(title)) + " characters out of 150 allowed)")

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