import mysql.connector, os
from mysql.connector import errorcode
from dotenv import load_dotenv

load_dotenv()

db_user = os.getenv("DB_USER")
db_pass = os.getenv("DB_PASS")
db_name = os.getenv("DB_NAME")
db_host = os.getenv("DB_HOST")

# Database connection config 
config = {
  'user': db_user,
  'password': db_pass,
  'host': db_host,
  'database': db_name
}

# Connect to the database
try:
  cnx = mysql.connector.connect(**config)
  cursor = cnx.cursor()  
except mysql.connector.Error as err:  
  if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
    print('Invalid credentials')
  elif err.errno == errorcode.ER_BAD_DB_ERROR:
    print('Database does not exist')
  else:
    print(err)
else:    
  # Create tables 
  with open('schema.sql','r') as sql:
    cursor.execute(sql.read())
    cnx.reconnect()
    cursor.close()

  cnx.commit()
  cursor = cnx.cursor()
  
  # Insert sample data
  add_post = ("INSERT INTO posts " 
              "(title, slug, content) "
              "VALUES (%s, %s, %s)")
  data = ('Example post', 'example-post', 'Content goes here')    
  
  cursor.execute(add_post, data)
  cnx.commit()
  
  cursor.close()
  cnx.close()
  
print('Done')