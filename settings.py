# Django settings for clickwork project.

import os

DEBUG = True
TEMPLATE_DEBUG = DEBUG

try:
    from local_settings import BASE_PATH
except ImportError:
    BASE_PATH = '.'

ADMINS = (
    # ('Your Name', 'your_email@domain.com'),
)

MANAGERS = ADMINS

DATABASES = {
    "default": {
        "NAME": "default_db",
        "ENGINE": "django.db.backends.postgresql_psycopg2"
        }
}

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = 'America/New_York'

DEFAULT_CHARSET="utf-8"

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-us'

SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# Absolute path to the directory that holds media.
# Example: "/home/media/media.lawrence.com/"
MEDIA_ROOT = os.path.join(BASE_PATH, '')

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash if there is a path component (optional in other cases).
# Examples: "http://media.lawrence.com", "http://example.com/media/"
MEDIA_URL = '/uploads/'

# URL prefix for admin media -- CSS, JavaScript and images. Make sure to use a
# trailing slash.
# Examples: "http://foo.com/media/", "/media/".
ADMIN_MEDIA_PREFIX = '/media/'

# Make this unique, and don't share it with anybody.
SECRET_KEY = '7wwt(!57n(mx5)@v61^(7#a66hhtq_*51sqn+6l78-t*f=d)45'

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
)

MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.middleware.transaction.TransactionMiddleware'
)

ROOT_URLCONF = 'clickwork.urls'

# List of strings corresponding to task types.
# These are the task types that are exercised by unit tests, so
# these are included by default.  To add others, change the
# TASK_TYPES variable in local_settings.py.
TASK_TYPES = ['simple']

TEMPLATE_DIRS = (
    # Put strings here, like "/home/html/django_templates" or "C:/www/django/templates".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
)

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.admin',
    'main',
    'user_management',
    #'django_hudson'
)

# should be changed if you're going to user management 
EMAIL_FROM = "Clickwork <clickwork@example.com>"

## Use this octal file permission number for the files
## in the archive that is created when a project is exported.
CLICKWORK_EXPORT_FILE_PERMISSIONS = 0444

## These are the usernames of people who should not both annotate the
## same task.  E.g., (("a", "b"), ("c", "d", "e")) means that if "a"
## is one annotator for a task, then "b" should not be the other, and
## if "c" is one annotator, then neither "d" nor "e" should be the
## other.
CLICKWORK_KEEP_APART = (("TEST_EXCLUSION_1", "TEST_EXCLUSION_2"),)

try:
    from local_settings import *
except ImportError:
    pass
