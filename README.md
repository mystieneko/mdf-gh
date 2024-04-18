
<img alt="MDFlare logo" src="./static/img/mdf_logo.png" width="400">

a simple blog system written in Flask with Markdown support

## Installation
### VPS
Create a virtual environment and activate it:  
```python3 -m venv venv && . venv/bin/activate```  
Install required packages:  
```pip install -r requirements.txt```  
### Shared hosting
If your shared hosting provider supports [WSGI](https://w.wiki/_vTN2), [FastCGI](https://w.wiki/9EeQ), or something similar, use it (technically any CGI protocol could work, but MDFlare was only tested with WSGI)

## Post-installation
Create a MySQL/MariaDB database and connect MDFlare to it (in `.env` file) OR import `mdflare.sql` file  
Then init the database:  
`flask init-db` (recommended) or `python3 init_db.py`  
Rename example configs and configure MDFlare how you like:  
```mv main.example.json main.json; mv cactus.example.json cactus.json```  
Then run it:  
`flask run` or `gunicorn -w 4 app:app` (assuming you have gunicorn installed)  
Login details for default admin account:  
**Login:** admin  
**Password:** changethispassword  

## Usage
Works on localhost:5000 or localhost:8000, may work in a production environment