import json
import re
import mysql.connector
import os
from constants import *

db_user = os.environ.get("DB_USER")
db_pass = os.environ.get("DB_PASS")
db_name = os.environ.get("DB_NAME")
db_host = os.environ.get("DB_HOST")

def loadJSON(config_name):
    with open(config_name, 'r', encoding="utf-8") as file:
        return json.load(file)

def saveJSON(config_dict, config_name):
    with open(config_name, 'w', encoding="utf-8") as file:
        json.dump(config_dict, file, indent=4)

def readPlainFile(file):
    if os.path.exists(file):
        with open(file, 'r', encoding="utf-8") as file:
            return file.read().splitlines()
    else:
        return []

config = loadJSON(MAIN_CONFIG_FILE)

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
               p.created, p.tags, p.authors, p.categories, DATE_FORMAT(p.created, %s) AS created
               FROM posts p WHERE p.slug = %s'''

    cursor.execute(query, (config['dateFormat'], slug,))
    row = cursor.fetchone()

    if row is None:
        cursor.close()
        conn.close()
        return None

    post = {
        "id": row[0],
        "title": row[1],
        "slug": row[2],
        "content": row[3],
        "created": row[4],
        "tags": row[5].split(','),
        "authors": row[6].split(','),
        "categories": row[7].split(','),
        "created_formatted": row[8]
    }
    print("(getPost) ", post)

    # If there are authors, fetch their details from the users table
    if post['authors']:
        placeholders = ', '.join(['%s'] * len(post['authors']))  # Create a string of placeholders
        author_query = f'''SELECT name, avatar_url FROM users WHERE name IN ({placeholders})'''
        cursor.execute(author_query, post['authors'])  # post['authors'] is already a tuple/list
        authors_info = cursor.fetchall()  # Fetch all matching rows

        # Optionally, process authors_info to structure it as needed
        post['author_details'] = [{'name': author[0], 'avatar_url': author[1]} for author in authors_info]

    cursor.close()
    conn.close()

    return post

def getAllPosts():
    conn = connect()
    cursor = conn.cursor()
    
    query = '''SELECT p.id, p.title, p.slug, p.content, 
                           p.created, p.tags, p.authors, p.categories,
                           DATE_FORMAT(p.created, %s) AS created_date  
                      FROM posts p
                      ORDER BY p.created DESC'''
               
    cursor.execute(query, (config['dateFormat'],))
    
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
           "categories": row[7].split(','),
           "created_formatted": row[8]
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
    elif filters and 'category' in filters:
        with_category = [post for post in posts if filters['category'] in post['categories']]
        return with_category
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

def gettheme():
    return session.get('theme') or config['theme']

def generateSlug(title):
    slug = re.sub(r'[^\w\s-]', '', title)
    slug = re.sub(r'\s+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    slug = re.sub(r'/+', '-', slug)
    slug = slug.lower()
    return slug

def cached(route):
    if config['cacheEnabled'] == "True":
        return cache.cached(timeout=config['cacheTimeout'])(route)
    return route
