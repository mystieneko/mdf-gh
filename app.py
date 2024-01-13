import sqlite3, mistune, os, re
from dotenv import load_dotenv
from flask import Flask, render_template, request, url_for, flash, redirect
from werkzeug.exceptions import abort

load_dotenv()

def getDbConnection():
	conn = sqlite3.connect('database.db')
	conn.row_factory = sqlite3.Row
	return conn

def getPost(slug):
    conn = getDbConnection()
    post = conn.execute('SELECT *, strftime("%m %d, %Y %H:%M", created) AS formatted_date FROM posts WHERE slug = ?',
                        (slug,)).fetchone()
    conn.close()
    if post is None:
        abort(404)
    return post

def generateSlug(title):
    slug = re.sub(r'[^\w\s]', '', title)
    slug = re.sub(r'\s+', '-', slug)
    slug = slug.lower()
    
    return slug

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("APP_SECRET")

@app.route('/')
def index():
	conn = getDbConnection()
	posts = conn.execute('SELECT * FROM posts').fetchall()
	conn.close()
	return render_template('index.html', posts=posts)

@app.route('/<slug>')
def post(slug):
    post = getPost(slug)
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
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        slug = generateSlug(title)

        if len(title) < 5 and title:
            flash('Title is too short!')
        elif not title:
            flash('Title is required!')
        else:
            conn = getDbConnection()
            conn.execute('INSERT INTO posts (title, content, slug) VALUES (?, ?, ?)',
                         (title, content, slug))
            conn.commit()
            conn.close()
            return redirect(url_for('index'))
    return render_template('create.html')

@app.route('/<slug>/edit', methods=('GET', 'POST'))
def edit(slug):
    post = getPost(slug)

    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']

        if len(title) < 5 and title:
            flash('Title is too short!')
        elif not title:
            flash('Title is required!')
        else:
            conn = getDbConnection()
            conn.execute('UPDATE posts SET title = ?, content = ?' ' WHERE slug = ?',
                         (title, content, slug))
            conn.commit()
            conn.close()
            return redirect(url_for('index'))

    return render_template('edit.html', post=post)

@app.route('/<slug>/delete', methods=('POST',))
def delete(slug):
    post = getPost(slug)
    conn = getDbConnection()
    conn.execute('DELETE FROM posts WHERE slug = ?', (slug,))
    conn.commit()
    conn.close()
    flash('"{}" was successfully deleted!'.format(post['title']))
    return redirect(url_for('index'))

@app.route('/about')
def about():
	return render_template('about.html')

@app.route('/roadmap')
def roadmap():
    return render_template('roadmap.html')