# flaskblog

a simple blog system written in flask with markdown support

## installation
create a virtual environment and activate it:  
`python3 -m venv venv`  
`. venv/bin/activate`  
install required packages:  
`pip install -r requirements.txt`  

## post-installation
create a mysql/mariadb database and connect flaskblog to it (in `.env` file)  
then init the database:  
`python3 init_db.py`  
rename example configs and configure flaskblog how you like:  
`mv config.example.json config.json; mv giscusConfig.example.json giscusConfig.json`  
then run it:  
`flask run` or `gunicorn -w 4 app:app` (assuming you have gunicorn installed)  

## usage
works on localhost:5000 or localhost:8000, may work in a production environment