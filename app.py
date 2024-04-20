from dotenv import load_dotenv
from flask import Flask, render_template, request, url_for, flash, redirect, session
from flask_caching import Cache
from markupsafe import Markup
from werkzeug.exceptions import abort
from werkzeug.utils import secure_filename
from functools import wraps
from bleach.sanitizer import Cleaner
from feedgen.feed import FeedGenerator
from pathlib import Path
from itsdangerous import URLSafeTimedSerializer
from mysql.connector import errorcode
from math import ceil
import smtplib
import ssl
import click
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import email.utils
import markupsafe
import mysql.connector
import mistune
import os
import re
import bcrypt
import time
import pytz
import json
import random
from functions import *
from constants import *

""" general stuff """

"""
this is needed to ensure that load_dotenv() loads .env file from the right
path, because load_dotenv() without arguments doesn't work with WSGI
"""
env_path = Path.cwd() / ".env"
# loading env variables
load_dotenv(dotenv_path=env_path)

# main config
config = loadJSON(MAIN_CONFIG_FILE)
# config for cactus.chat (for post comments)
cactusConfig = loadJSON(CACTUS_CONFIG_FILE)
# config values are strings, so we need to convert some of them to integers
config['cacheTimeout'] = int(config['cacheTimeout'])

# cache config for cached routes
cache_config = {
    "DEBUG": True,
    "CACHE_TYPE": "SimpleCache",
    "CACHE_DEFAULT_TIMEOUT": 300
}


app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get("APP_SECRET")
serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
app.config.from_mapping(cache_config)
app.config.from_mapping(config)
app.config.update(config)
app.config["AUTOESCAPE"] = True
cache = Cache(app)

# if no preferred theme found, default to auto.css
@app.before_request
def before_request():
    if not session.get('theme'):
        session['theme'] = 'auto.css'

# making a list of themes from ./static/css/themes directory
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

""" cli commands """

def create_database(cursor, dbname):
    try:
        cursor.execute("CREATE DATABASE {} DEFAULT CHARACTER SET 'utf8'".format(dbname))
        print("Database {} created successfully.".format(dbname))
    except mysql.connector.Error as err:
        print("Failed creating database: {}".format(err))
        exit(1)

@app.cli.command("init-db")
def initdb():
    dbname = input("Enter database name (default: mdflare): ")
    # if dbname is empty, default to "mdflare"
    if not dbname:
        dbname = "mdflare"

    db_user = os.environ.get("DB_USER")
    db_pass = os.environ.get("DB_PASS")
    os.environ["DB_NAME"] = dbname
    db_host = os.environ.get("DB_HOST")

    # Database connection config 
    config = {
        'user': db_user,
        'password': db_pass,
        'host': db_host,
        'database': dbname
    }

    # Connect to the database
    print(f"Connecting to database {dbname} ...")
    try:
        cnx = mysql.connector.connect(**config)
        cursor = cnx.cursor()
        app.logger.info("Successfully connected to database %s", dbname)
    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR: # if "access denied" error occurred
            app.logger.error('Invalid credentials')
        elif err.errno == errorcode.ER_BAD_DB_ERROR:
            cnx = mysql.connector.connect(user=db_user, password=db_pass, host=db_host, database='mysql')
            cursor = cnx.cursor()
            create_database(cursor, dbname)
            cnx.database = dbname
        else:
            app.logger.error(err)
            return
    else:
        cursor.close()
        cnx.close()

    # Reconnect to the newly created database
    try:
        cnx = mysql.connector.connect(**config)
        cursor = cnx.cursor()
        app.logger.info("Successfully connected to database %s", dbname)
    except mysql.connector.Error as err:
        app.logger.error(err)
        return

    # Create tables
    with open('schema.sql', 'r') as sql_file:
        sql_script = sql_file.read()
        try:
            cursor.execute(sql_script)
            print('Database %s was successfully initialized!' % dbname)
        except mysql.connector.Error as err:
            app.logger.error("Failed to initialize database %s: %s", dbname, err)
        finally:
            if cursor:
                cursor.close()
            if cnx:
                cnx.close()

""" error handlers """

@app.errorhandler(404)
def notfound(error):
    return render_template('errorpages/404.html'), 404

@app.errorhandler(403)
def forbidden(error):
    return render_template('errorpages/403.html'), 403

@app.errorhandler(500)
def internalservererror(error):
    return render_template('errorpages/500.html'), 500

""" context processors """

@app.context_processor
def inject_translations():
    lang = session.get('lang') or config['defaultLangShort'] or 'en'
    translations = loadJSON(f"translations/strings_{lang}.json")
    return dict(translations=translations, lang=lang)

@app.context_processor
def inject_version():
    return dict(version=VERSION, version_mod_left=VERSION_MOD_LEFT, version_mod_right=VERSION_MOD_RIGHT, app_name=APP_NAME)

@app.context_processor
def inject_theme():
    return dict(theme_name=session.get('theme'), themes=themes)

@app.context_processor
def inject_tohtml():
    return dict(to_html=mistune.html)

app.context_processor(inject_version)

# template filter for converting markdown to html
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

""" routes """

""" admin routes """

@app.route('/admin/', methods=['GET', 'POST'])
def admin():
    # if user is not logged in and is not an administrator, throw a 403 error
    if not (session.get('user') and session['user_role'] == 'administrator'):
        abort(403)
    if request.method == 'POST':
        # Save changes
        config = loadJSON(MAIN_CONFIG_FILE)
        for key in config.keys():
            if key in request.form:
                # Update the config dictionary with the new value
                config[key] = request.form[key]
        saveJSON(config, MAIN_CONFIG_FILE)
        app.config.update(config)
        flash('Changes saved!', 'success')
        return redirect(url_for('admin'))
    else:
        # Render the admin page with editable inputs
        config_vars = loadJSON(MAIN_CONFIG_FILE)
        return render_template('admin/index.html', config_vars=config_vars)

@app.route('/admin/users/', methods=['GET', 'POST'])
def admin_users():
    if not (session.get('user') and session['user_role'] == 'administrator'):
        abort(403)

    conn = connect()
    cursor = conn.cursor()

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'update_username':
            new_username = request.form['new_username']
            user_id = request.form['user_id']
            cursor.execute('UPDATE users SET name=%s WHERE id=%s', (new_username, user_id))
            conn.commit()

        elif action == 'update_email':
            new_email = request.form['new_email']
            user_id = request.form['user_id']
            cursor.execute('UPDATE users SET email=%s WHERE id=%s', (new_email, user_id))
            conn.commit()

        elif action == 'change_password':
            new_password = request.form['newpass']
            confirm_password = request.form['newpassconfirm']
            user_id = request.form['user_id']
                
            if new_password != confirm_password:
                flash('Passwords do not match')
                
            new_hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
            
            query = """UPDATE users
                    SET password=%s
                    WHERE id=%s"""

            cursor.execute(query, (new_hashed_password, user_id))
            conn.commit()

        elif action == 'update_role':
            new_role = request.form['new_role']
            user_id = request.form['user_id']
            cursor.execute('UPDATE users SET role=%s WHERE id=%s', (new_role, user_id))
            conn.commit()

        elif action == 'delete_user':
            user_id = request.form['user_id']
            cursor.execute('DELETE FROM users WHERE id=%s', (user_id,))
            conn.commit()

        elif action == 'update_approval':
            new_approval = request.form['new_approval']
            user_id = request.form['user_id']
            cursor.execute('UPDATE users SET is_approved=%s WHERE id=%s', (new_approval, user_id))
            conn.commit()

        # Add more actions for approving/rejecting users, updating passwords, etc.

    cursor.execute('SELECT id, name, email, password, is_approved, role, avatar_url, bio FROM users')
    users = []
    # id  name    email   password    is_approved role    avatar_url  bio 
    for row in cursor:
        user = {
            'id': row[0],
            'name': row[1],
            'email': row[2],
            'password': row[3],
            'is_approved': row[4],
            'role': row[5],
            'avatar_url': row[6],
            'bio': row[7]
        }
        users.append(user)
    cursor.close()
    conn.close()

    return render_template('admin/users.html', users=users)

@app.route('/admin/currentconfig/')
def admin_currentconf():
    if not (session.get('user') and session['user_role'] == 'administrator'):
        abort(403)

    config_vars = loadJSON(MAIN_CONFIG_FILE)

    return render_template('admin/currentconf.html', config=config_vars)

""" account routes """

@app.route('/account/', methods=['GET', 'POST'])
def accountSettings():
    if not session.get('user'):
        return redirect(url_for('login'))
    return redirect(url_for('profileSettings'))

@app.route('/account/profile/', methods=['GET', 'POST'])
def profileSettings():
    if not session.get('user'):
        return redirect(url_for('login'))

    conn = connect()
    cursor = conn.cursor()

    if request.method == "POST":
        new_username = request.form['newusername']
        if new_username != session['user']:
            # check if new username is available
            cursor.execute('''SELECT name FROM users WHERE name=%s''', (new_username,))
            username_exists = cursor.fetchone()

            if username_exists:
                flash('This username is already taken')
                return render_template('account/profile.html')

            # update username
            update_sql = """UPDATE users SET name=%s WHERE name=%s"""
            cursor.execute(update_sql, (new_username, session['user']))
            
            conn.commit()
            cursor.close()
            conn.close()

            flash('Username changed successfully!')
            session['user'] = new_username
            return redirect(request.referrer)

        new_bio = request.form['bio']
        cursor.execute('''SELECT bio FROM users WHERE name=%s''', (session['user'],))
        stored_bio = cursor.fetchone()
        if new_bio != stored_bio:
            update_sql = """UPDATE users SET bio=%s WHERE name=%s"""
            cursor.execute(update_sql, (new_bio, session['user']))
            
            conn.commit()

    cursor.execute('''SELECT avatar_url, bio FROM users  
        WHERE name=%s''', (session['user'],))
    row = cursor.fetchone()

    user = {
        'avatar': row[0],
        'bio': row[1]
    }
    cursor.close()
    conn.close()
    return render_template('account/profile.html', user=user)

@app.route('/account/change_avatar/', methods=['POST'])
def changeAvatar():
    conn = connect()
    cursor = conn.cursor()
    avatar_file = request.files['avatar']
    if avatar_file:
        filename = secure_filename(avatar_file.filename)
        file_extension = os.path.splitext(filename)[1]
        new_filename = f"{session['user']}{file_extension}"
        avatar_absolute_path = os.path.join(f'{Path.cwd()}/static/avatars/', new_filename)
        avatar_file.save(avatar_absolute_path)
        avatar_relative_path = os.path.join('/static/avatars/', new_filename)

        cursor.execute("""UPDATE users
            SET avatar_url=%s
            WHERE name=%s""", (avatar_relative_path, session['user'],))
    cursor.close()
    conn.close()
    return redirect(request.referrer)

@app.route('/account/delete_current_avatar/', methods=['POST'])
def deleteCurrentAvatar():
    conn = connect()
    cursor = conn.cursor()

    # Fetch the current avatar URL from the database
    cursor.execute("""SELECT avatar_url FROM users WHERE name=%s""", (session['user'],))
    result = cursor.fetchone()
    if result and result[0] != '/static/avatars/default.svg':
        current_avatar_url = result[0]
        # Convert the relative path to an absolute path
        current_avatar_path = os.path.join(Path.cwd(), current_avatar_url.strip('/'))

        # Check if the file exists and is not the default avatar, then delete it
        if os.path.isfile(current_avatar_path) and 'default.svg' not in current_avatar_path:
            os.remove(current_avatar_path)

    # Update the user's avatar URL to the default avatar
    cursor.execute("""UPDATE users
                      SET avatar_url="/static/avatars/default.svg"
                      WHERE name=%s""", (session['user'],))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(request.referrer)

@app.route('/account/security/')
def accountSecurity():
    if not session.get('user'):
        return redirect(url_for('login'))
    return render_template('account/security.html')

@app.route('/account/authentication/')
def accountAuth():
    if not session.get('user'):
        return redirect(url_for('login'))

    return redirect(url_for('profileSettings'))

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
        
        if current_password and not bcrypt.checkpw(current_password.encode('utf-8'), user[3].encode('utf-8')):
            flash('Password is incorrect')
            return redirect(url_for('accountSecurity'))
        elif not current_password:
            flash('Enter your password for confirmation')
            return redirect(url_for('accountSecurity'))

        # delete account
        delete_sql = """DELETE FROM users WHERE name=%s"""
        cursor.execute(delete_sql, [session['user']])
        
        conn.commit()
        cursor.close()
        conn.close()

        session.pop('user', None)
        flash('Your account was successfully deleted.')
        return redirect(url_for('login'))

""" author routes """

@app.route('/a/<author>/')
def showAuthor(author):
    conn = connect()
    cursor = conn.cursor()
    cursor.execute('''SELECT name, role, avatar_url, bio FROM users  
        WHERE name=%s''', (author,))
    row = cursor.fetchone()
    if not row:
        abort(404)
    author_ = {
        'name': row[0],
        'role': row[1],
        'avatar': row[2],
        'bio': row[3]
    }
    author_['role'] = author_['role'].capitalize()

    cursor.execute('''SELECT slug, title, IF(LENGTH(content) > 300,CONCAT(LEFT(content,300),'...'),
content), created, DATE_FORMAT(created, %s) AS created_date FROM posts 
                      WHERE authors LIKE %s ORDER BY created DESC''', (config['dateFormat'], '%' + author + '%',))
    posts = [{'slug': row[0], 'title': row[1], 'content': row[2], 'created': row[3], 'created_formatted': row[4]} for row in cursor.fetchall()]
    posts_count = len(posts)
    cursor.close()
    conn.close()

    return render_template('author/profile.html', author=author_, posts=posts, posts_count=posts_count)

user_requests = {}

""" auth routes """

@app.route('/signup/', methods=['GET', 'POST'])
def register():
    if config["registrationsOpened"] == "True":
        # if session.get('user'):
        #     flash("Why are you trying to register while logged in???")
        #     return redirect(url_for('index'))
        num1 = random.randint(1, 20)
        num2 = random.randint(1, 20)
        operator = random.choice(['+', '-'])
        expression = f"{num1} {operator} {num2}"
        if operator == '+':
            result = num1 + num2
        elif operator == '-':
            # Ensure num1 is greater than or equal to num2
            num1, num2 = max(num1, num2), min(num1, num2)
            result = num1 - num2

        if request.method == 'POST':
            user_ip = request.remote_addr

            now = time.time()
            if user_ip not in user_requests:
                user_requests[user_ip] = []

            user_requests[user_ip] = [t for t in user_requests[user_ip] if now - t < 86400]

            if len(user_requests[user_ip]) >= int(config['registerRequestLimit']):
                abort(429)

            user_requests[user_ip].append(now)

            name = request.form['name']
            email = request.form['email']
            email_regex = r'^\w+[\+\.\w-]*@([\w-]+\.)*\w+[\w-]*\.([a-z]{2,24}|\d+)$'

            if not re.match(email_regex, email):
                flash('Invalid email')
                return redirect(url_for('register'))

            password = request.form['password']
            confirm_password = request.form['confirm_password']
            if (password != confirm_password):
                flash('Passwords do not match!')
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

            captcha = int(request.form['captcha'])

            if captcha != 15:
                flash('Incorrect CAPTCHA, please try again.')
                return redirect(url_for('register'))

            #role = request.form['role']
            #if not role:
            #    flash('Choose a role')
            #    return redirect(url_for('register'))
            role = 'user'
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
            if config['requireAccountApproval'] == "True":
                if config['adminContact'] != "":
                    message = Markup('"{}" was registered! If you want it approved, <a href="' + config["adminContact"] + '">contact the admin</a>').format(name)
                else:
                    message = Markup('"{}" was registered! If you want it approved, contact the admin').format(name)
            else:
                message = Markup('"{}" was registered, you can now log in into your account.').format(name)
            flash(message)

            return redirect(url_for('index'))

        return render_template('auth/register.html', expression=expression)
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

        if user and (config['requireAccountApproval'] == "False" or user[4] == 1 or (user[5] == 'user')) and bcrypt.checkpw(password.encode('utf-8'), user[3].encode('utf-8')):
            remember_me = request.form.get('remember_me')
            if remember_me:
                # Set session to be permanent (expire after 30 days)
                session.permanent = True
                #app.permanent_session_lifetime = timedelta(days=30)
            else:
                # Set session to expire when the browser is closed
                session.permanent = False

            # If valid credentials, set user in session
            session['user'] = name
            session['user_approved'] = 1
            session['user_id'] = user[0]
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
    return render_template('auth/login.html')

@app.route('/forgot_password/', methods=['GET', 'POST'])
def forgotPassword():
    if request.method == "POST":
        email_ = request.form['email']
        conn = connect()
        cursor = conn.cursor()
        cursor.execute('''SELECT * FROM users  
                          WHERE email=%s''', (email_,))
        user = cursor.fetchone()
        # user[1] == name, user[2] == email, user[3] == password, user[4] == is_approved, user[5] == role
        if user:
            token = serializer.dumps(email_)
            # Send email with the reset link containing the token
            # You need to implement this part using an email service provider
            reset_link = url_for('resetPassword', token=token, _external=True)
            sender_email = os.environ.get("EMAIL_ADDRESS")  # Your email address
            receiver_email = email_ # Recipient's email address
            password = os.environ.get("EMAIL_PASSWORD")  # Retrieve email password from environment variable

            # Create a multipart message
            message = MIMEMultipart("alternative")
            message["Subject"] = "Password Reset Request"
            message["From"] = sender_email
            message["To"] = receiver_email
            message_id = email.utils.make_msgid()
            message["Message-ID"] = message_id
            email_server = os.environ.get("EMAIL_SERVER")
            smtp_port = os.environ.get("SMTP_PORT")

            # Create the plain-text and HTML version of your message
            text = f"""\
            Dear {user[1]},

            We received a request to reset the password associated with your account. If you did not request this change, please disregard this email. Otherwise, please follow the instructions below to reset your password:

            To reset your password, please click on the following link: {reset_link}

            This link will expire in 1 hour, so please reset your password promptly.

            Thank you,
            {config['blogName']} Team
            """
            html = f"""\
            <html>
            <body>
                <p>Dear {user[1]},</p>
                <p>We received a request to reset the password associated with your account. If you did not request this change, please disregard this email. Otherwise, please follow the instructions below to reset your password:</p>
                <p>To reset your password, please click on the following link:</p>
                <p><a href="{reset_link}">Password Reset Link</a></p>
                <p>If the link doesn't work, try this URL: {reset_link}</p>
                <p>This link will expire in 1 hour, so please reset your password promptly.</p>
                <p>Thank you,<br>{config['blogName']} Team</p>
            </body>
            </html>
            """

            # Turn these into plain/html MIMEText objects
            part1 = MIMEText(text, "plain")
            part2 = MIMEText(html, "html")

            # Attach parts into message container
            message.attach(part1)
            message.attach(part2)

            # Create a secure SSL context
            context = ssl.create_default_context()

            # Try to log in to server and send email
            try:
                with smtplib.SMTP_SSL(email_server, smtp_port, context=context) as server:
                    server.login(sender_email, password)
                    server.sendmail(sender_email, receiver_email, message.as_string())
                flash("An email containing password reset instructions was sent to your inbox. If it doesn't appear there, check the 'Spam' folder in your email provider.")
            except Exception as e:
                flash(f"Failed to send email. Error: {e}")
            cursor.close()
            conn.close()
        else:
            flash('Something went wrong')
    return render_template('auth/forgotPassword.html')


@app.route('/reset_password/<token>/', methods=['GET', 'POST'])
def resetPassword(token):
    try:
        email_ = serializer.loads(token, max_age=3600)  # Token expires after 1 hour
    except:
        # Invalid or expired token
        flash('Invalid/expired token')
        return redirect(url_for('forgotPassword'))

    if request.method == "POST":
        conn = connect()
        cursor = conn.cursor()
        password = request.form['password']
        passconfirm = request.form['passconfirm']
        if password != passconfirm:
            flash('Passwords do not match')

        # Update the user's password in the database
            
        if password != passconfirm:
            flash('New passwords do not match')
            return render_template('account/base.html')
            
        new_hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        
        query = """UPDATE users
                SET password=%s
                WHERE email=%s"""

        cursor.execute(query, (new_hashed_password, email_))
        conn.commit()
        cursor.close()
        conn.close()
        # Redirect to a success page
        return redirect(url_for('passwordResetSuccess'))
    return render_template('auth/resetPassword.html')

# @app.route('/password_reset_confirmation/')
# def passwordResetConfirmation():
#     return render_template('auth/passwordResetConfirmation.html')

@app.route('/password_reset_success/')
def passwordResetSuccess():
    return render_template('auth/passwordResetSuccess.html')

@app.route('/logout/')  
def logout():
    if session.get('user'):
        session.pop('user', None)
        session.pop('user_approved', None)
        session.pop('user_role', None)
    return redirect(request.referrer)

""" general routes """

@app.route('/')
def index():
    if config['minimalMode'] == "True":
        return redirect(url_for('posts'))
    return render_template('index.html', to_html=mistune.html)

@app.route("/feed/")
def rssFeed():
    fg = FeedGenerator()
    fg.title(config['blogName'])
    blog_desc = config['blogDesc']
    if not blog_desc:
        blog_desc = config.get('defaultDesc', '<no description>')
        print(blog_desc)
    formatted_desc = render_markdown(blog_desc)
    fg.description(formatted_desc)
    fg.link(href=config['blogDomain'])
    
    posts = getAllPosts() # Custom query to get all posts

    conn = connect()
    cursor = conn.cursor()
    
    for post in posts:
        fe = fg.add_entry()
        fe.id(str(post['id']))
        fe.title(post['title'])
        formatted_content = render_markdown(post['content'])
        fe.link(href=url_for("post", slug=post["slug"]))
        fe.pubDate(str(pytz.utc.localize(post["created"])))
        
        if post['authors']:
            placeholders = ', '.join(['%s'] * len(post['authors']))
            author_query = f'''SELECT name FROM users WHERE name IN ({placeholders})'''
            cursor.execute(author_query, post['authors'])
            authors_info = cursor.fetchall()
            author_info = [{'name': author[0]} for author in authors_info]
            author_names = ', '.join(author[0] for author in authors_info)
            formatted_content = f"Authors: {author_names}\n\n{formatted_content}"
            for author in author_info:
                print(author['name'])
                fg.author(name=author['name'])
                fg.contributor(name=author['name'])
        fe.content(formatted_content)

    cursor.close()
    conn.close()

    return fg.rss_str(pretty=True)


@app.route('/about/')
def about():
    return render_template('about.html')

@app.route('/change_lang/', methods=['POST'])
def changeLang():
    lang = request.form['language']
    session['lang'] = lang
    return redirect(request.referrer)

@app.route('/change_theme/', methods=['POST'])
def changeTheme():
    theme = request.form['theme-change']
    session['theme'] = theme
    return redirect(request.referrer)

""" posts """

@app.route('/posts/')
@cached
def posts():
    page_number = int(request.args.get('page', 1))  # Get the page number from the query parameter, default to 1
    per_page = int(config['postsPerPage'])  # Number of posts per page

    conn = connect()
    cursor = conn.cursor()
    
    # Calculate the offset based on the page number
    offset = (page_number - 1) * per_page

    query = '''SELECT p.id, IF(LENGTH(title) > 150,CONCAT(LEFT(p.title,150),'...'), p.title), p.slug, IF(LENGTH(content) > 150,CONCAT(LEFT(p.content,150),'...'),
                p.content), 
            p.created, p.tags, p.authors,
            DATE_FORMAT(p.created, %s) AS created_date  
            FROM posts p
            ORDER BY p.created DESC
            LIMIT %s OFFSET %s'''  # Add LIMIT and OFFSET for pagination
               
    cursor.execute(query, (config['dateFormat'], per_page, offset))
    
    posts = []
    
    for row in cursor:
        post = {
           "id": row[0],
           "title": row[1],
           "slug": row[2],
           "content": row[3],
           "created": row[4],
           "tags": row[5].split(','),
           "authors": row[6].split(','),
           "created_formatted": row[7]
        }
        posts.append(post)

    author = []
    for post in posts:
        if post['authors']:
            placeholders = ', '.join(['%s'] * len(post['authors']))  # Create a string of placeholders
            author_query = f'''SELECT name, avatar_url FROM users WHERE name IN ({placeholders})'''
            cursor.execute(author_query, post['authors'])  # post['authors'] is already a tuple/list
            authors_info = cursor.fetchall()  # Fetch all matching rows

            # Optionally, process authors_info to structure it as needed
            author_info = [{'name': author[0], 'avatar_url': author[1]} for author in authors_info]
            author.append(author_info)

    # Get total count of posts
    cursor.execute("SELECT COUNT(*) FROM posts")
    total_posts = cursor.fetchone()[0]
    total_pages = ceil(total_posts / per_page)


    cursor.close()
    conn.close()

    return render_template('post/list.html', posts=posts, posts_count=total_posts, author=author, page_number=page_number, total_pages=total_pages)

@app.route('/new/', methods=['GET', 'POST'])
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

            authors_str = request.form['authors']
            authors_str = authors_str.lower().strip()
            authors = authors_str.split(',')
            authors = [a.strip() for a in authors]

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
            if len(title) < int(config['minimumTitleLength']):
                flash('Title is too short!')
                return redirect(url_for('create'))
            if len(title) > int(config["titleLengthLimit"]):
                flash('Title is too long! (' + str(len(title)) + " characters out of " + config["titleLengthLimit"] + " allowed)")
            if len(slug) > int(config["slugLengthLimit"]):
                flash('Slug is too long! (' + str(len(slug)) + " characters out of " + config["slugLengthLimit"] + " allowed)")

            else:
                conn = connect()
                cursor = conn.cursor()
                tags_str = ','.join(tags)
                authors_str = ','.join(authors)

                insert_sql = """INSERT INTO posts  
                (title, content, slug, tags, authors)
                VALUES (%s, %s, %s, %s, %s)"""

                cursor.execute(insert_sql, (title, content, slug, tags_str, authors_str))
                conn.commit()

                cursor.close()
                conn.close()

                flash('Post created!')
                return redirect(url_for('post', slug=slug))
        return render_template('post/create.html')
    else:
        abort(403)

@app.route('/<slug>/edit/', methods=['GET', 'POST'])
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
            new_authors_str = request.form['authors']
            new_authors_str = new_authors_str.lower().strip()
            new_authors = [a.strip() for a in new_authors_str.split(',')]

            if newslug:
                newslug = generateSlug(newslug)
            else:
                newslug = generateSlug(title)

            if not title:
                flash('Title is required!')
            if len(title) < 5:
                flash('Title is too short!')
            if len(title) > int(config["titleLengthLimit"]):
                flash('Title is too long! (' + str(len(title)) + " characters out of " + config["titleLengthLimit"] + " allowed)")
            if len(newslug) > int(config["slugLengthLimit"]):
                flash('Slug is too long! (' + str(len(slug)) + " characters out of " + config["slugLengthLimit"] + " allowed)")
                
            else:
                conn = connect()
                cursor = conn.cursor()
                
                sql = """UPDATE posts  
                         SET title=%s, content=%s, slug=%s, tags=%s, authors=%s
                         WHERE slug=%s"""
                 
                cursor.execute(sql, (title, content, newslug, ','.join(new_tags), ','.join(new_authors), slug))
                conn.commit()
                
                cursor.close()
                conn.close()
                
                return redirect(url_for('post', slug=newslug))
                 
        return render_template('post/edit.html', post=post)
    else:
        abort(403)

@app.route('/<slug>/delete/', methods=['POST'])
def delete(slug):

    post = getPost(slug)
    if post is None:
        abort(404)
    conn = connect()  
    cursor = conn.cursor()

    delete_sql = """DELETE FROM posts  
                    WHERE slug = %s"""
    
    cursor.execute(delete_sql, (slug,))
    conn.commit()
    cursor.close()
    conn.close()

    flash('"{}" was successfully deleted!'.format(post['title']))
    
    return redirect(url_for('posts'))

@app.route('/search/')
@cached
def search():
    if config['searchEnabled'] == "True":
        search_query = request.args.get('q', '')
        if search_query == '' or search_query == ' ':
            flash("Search query cannot be empty")
            return redirect(request.referrer)

        conn = connect()
        cursor = conn.cursor()

        query = '''SELECT id, title, slug, IF(LENGTH(content) > 300,CONCAT(LEFT(content,300),'...'),
                    content), created, DATE_FORMAT(created, %s) AS created_date  
                   FROM posts WHERE title LIKE %s
                   ORDER BY 
                       CASE 
                           WHEN title = %s THEN 1  -- Exact match in title
                           WHEN title LIKE %s THEN 2  -- Partial match in title
                           ELSE 3  -- Match in content
                       END, created DESC'''
        cursor.execute(query, (config['dateFormat'], '%' + search_query + '%', search_query, '%' + search_query + '%',))
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

        return render_template('search_results.html', posts=posts, posts_count=posts_count, search_query=search_query)
    else:
        return abort(404)

@app.route('/tag/<tag>/')
@cached
def tag(tag):

    posts = getPosts({'tag': tag})
    posts_count = len(getPosts({'tag': tag}))
  
    return render_template('tag.html', posts=posts, tag=tag, posts_count=posts_count)

@app.route('/<slug>/')
@cached
def post(slug):
    post = getPost(slug)
    if post is None:
        return abort(404)
    return render_template('post/view.html', post=post, to_html=mistune.html, cactus=cactusConfig)

""" pages """

@app.route('/pages/')
@cached
def pages():
    if config['showPages'] == "True":
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
        abort(404)

@app.route('/new/page/', methods=['GET', 'POST'])
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
            if len(title) > int(config["titleLengthLimit"]):
                flash('Title is too long! (' + str(len(title)) + " characters out of " + config["titleLengthLimit"] + " allowed)")
            if len(slug) > int(config["slugLengthLimit"]):
                flash('Slug is too long! (' + str(len(slug)) + " characters out of " + config["slugLengthLimit"] + " allowed)")

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

@app.route('/p/<slug>/')
@cached
def page(slug):
    page = getPage(slug)
    if page is None:
        return abort(404)
    return render_template('page/view.html', page=page, to_html=mistune.html)

@app.route('/p/<slug>/edit/', methods=['GET', 'POST'])
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
            if len(title) > int(config["titleLengthLimit"]):
                flash('Title is too long! (' + str(len(title)) + " characters out of " + config["titleLengthLimit"] + " allowed)")
            if len(newslug) > int(config["slugLengthLimit"]):
                flash('Slug is too long! (' + str(len(slug)) + " characters out of " + config["slugLengthLimit"] + " allowed)")
                
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

@app.route('/p/<slug>/delete/', methods=['POST'])
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
    
    return redirect(url_for('pages'))