# all private values are stored in .env file, not here

class Config:
    SITE_NAME = "Blog Name" # blog name
    BLOG_DESC = "" # blog description
    DEFAULT_DESC = "## If you see this message, congratulations, FlaskBlog is installed successfully!\n\n**Further configuration is required.**\n\nYou can now register your account, give it posting perms via [phpMyAdmin](https://www.phpmyadmin.net/) and start writing!\n\nYou can also disable registration afterwards to not let random people register to your blog.\n\n**Note:** This is the default description, which appears if `BLOG_DESC` variable is not set.\n"
    REGISTRATIONS_OPENED = True # whether registrations are opened or not: True = opened, False = closed
    REGISTER_REQUEST_LIMIT = 3 # how many accounts can one user register per day
    TITLE_LENGTH_LIMIT = 150 # how long can post title be (in symbols count)
    THEME = "default" # the theme to use from /static/css/themes/ folder
    ICON_URL = "/static/img/flask.svg" # url for blog icon & favicon, you can use either a relative url, or an absolute url
    ADMIN_CONTACT = "" # admin contact, will be used as a way of contacting the admin to get new account approved
    CACHE_ENABLED = False # whether cache is enabled or not
    POSTS_CACHE_TIMEOUT = 3600 # for how long do you want to cache the posts, in seconds (only works if CACHE_ENABLED is True)

class GiscusConfig:
    INSTANCE = ""
    REPO = ""
    REPO_ID = ""
    CATEGORY = ""
    CATEGORY_ID = ""
    MAPPING = ""
    STRICT = ""
    REACTIONS_ENABLED = ""
    EMIT_METADATA = ""
    INPUT_POSITION = ""
    THEME = ""
    LANG = ""
    LOADING = ""