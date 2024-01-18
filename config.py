# all private values are stored in .env file, not here

class Config:
    SITE_NAME = "Blog Name" # name of your blog
    BLOG_DESC = ""
    DEFAULT_DESC = "### If you see this message, congratulations, FlaskBlog is installed successfully!\n\n**Further configuration is required.**\n\nYou can now register your account, give it posting perms via [phpMyAdmin](https://www.phpmyadmin.net/) and start writing!\n\nYou can also disable registration afterwards to not let random people register to your blog.\n\n**Note:** This is the default description, which appears if `BLOG_DESC` variable is not set.\n"
    REGISTRATIONS_OPENED = 1
    ICON_URL = "/static/img/flask.svg" # you can use either a relative url, or an absolute url
    ADMIN_EMAIL = "" # this email will be used as a way of contacting the admin to get new account approved