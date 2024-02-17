<img alt="FlaskBlog logo" src="./static/img/flb_logo_full_w.png" width="400">

a simple blog system written in Flask with Markdown support

## Installation
Create a virtual environment and activate it:  
```python3 -m venv venv && . venv/bin/activate```  
Install required packages:  
```pip install -r requirements.txt```  

## Post-installation
Create a MySQL/MariaDB database and connect FlaskBlog to it (in `.env` file)  
Then init the database:  
```python3 init_db.py```  
Rename example configs and configure FlaskBlog how you like:  
```mv config.example.json config.json; mv giscusConfig.example.json giscusConfig.json```  
Then run it:  
`flask run` or `gunicorn -w 4 app:app` (assuming you have gunicorn installed)  

## Usage
Works on localhost:5000 or localhost:8000, may work in a production environment