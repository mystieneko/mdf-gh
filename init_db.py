import sqlite3

connection = sqlite3.connect('database.db')


with open('schema.sql') as f:
	connection.executescript(f.read())

	cur = connection.cursor()

	cur.execute("INSERT INTO posts (title, slug, content) VALUES (?, ?, ?)",
		('Welcome to FlaskBlog!', 'welcome', 'If you see this post, congratulations, FlaskBlog is installed and working correctly, you may delete this post and start writing your own ones!')
		)

	connection.commit()
	connection.close()