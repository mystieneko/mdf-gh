# all private values are stored in .env file, not here

class Config:
    SITE_NAME = "Blog Name" # blog name
    BLOG_DESC = "" # blog description
    DEFAULT_DESC = "## If you see this message, congratulations, FlaskBlog is installed successfully!\n\n**Further configuration is required.**\n\nYou can now register your account, give it posting perms via [phpMyAdmin](https://www.phpmyadmin.net/) and start writing!\n\nYou can also disable registration afterwards to not let random people register to your blog.\n\n**Note:** This is the default description, which appears if `BLOG_DESC` variable is not set.\n"
    REGISTRATIONS_OPENED = True # whether registrations are opened or not: True = opened, False = closed
    REGISTER_REQUEST_LIMIT = 3 # how many accounts can one user register per day
    THEME = "default" # the theme to use from /static/css/themes/ folder
    ICON_URL = "/static/img/flask.svg" # url for blog icon & favicon, you can use either a relative url, or an absolute url
    ADMIN_CONTACT = "" # admin contact, will be used as a way of contacting the admin to get new account approved
    CACHE_ENABLED = False # whether cache is enabled or not
    POSTS_CACHE_TIMEOUT = 3600 # for how long do you want to cache the posts, in seconds (only works if CACHE_ENABLED is True)

class GiscusConfig:
    INSTANCE = "giscus.app"
    REPO = "mystieneko/flaskblog-comments"
    REPO_ID = "R_kgDOKc973A"
    CATEGORY = "Announcements"
    CATEGORY_ID = "DIC_kwDOKc973M4CZ7Os"
    MAPPING = "pathname"
    STRICT = "0"
    REACTIONS_ENABLED = "1"
    EMIT_METADATA = "0"
    INPUT_POSITION = "top"
    THEME = "light"
    LANG = "en"
    LOADING = "lazy"