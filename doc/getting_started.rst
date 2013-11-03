Getting Started
===============

Set up the Server
-----------------

To set up the Clickwork server, you must first have
Django installed::

   $ easy_install Django

(Clickwork requires Django 1.3+, PostgreSQL, geopy, and
python-markdown.)

Once you've done that, you can check out Clickwork::

   $ git clone https://github.com/clickwork/clickwork.git
   
Edit your local_settings.py file (inside clickwork) to set your 
BASE_PATH; this path should match the file location of your current
checkout, so something like "/home/user/clickwork/".

Run "createdb default_db" from the command line to create the
PostgreSQL database that Clickwork will talk to.  (You can edit
local_settings.py to make the default database have a different name,
but it needs to be PostgreSQL, because some of the pages use
PostgreSQL-specific SQL functions.)

To populate the database, inside your Clickwork directory, run the syncdb
command from manage.py::

    $ python manage.py syncdb

You should configure an admin user for yourself::

    $ python manage.py createsuperuser

Once this is done, you should be able to start up the built in Django
webserver::

    $ python manage.py runserver

Then visit http://localhost:8000/ , login with your username/password just
created, and you should see: "0 tasks to tag; 0 tasks to merge."

Creating a Project
------------------

Currently, to create a project, one must use the admin interface. Go to::

    http://localhost:8000/admin/

From there, click the "Projects" link, then "Add Project". Enter a title
and description. Select 'simple' from the Type dropdown. Assign yourself
as administrator, enter 1 for annotator. Set the priority to Medium.

You will need to create a group (by clicking the green + icon) for each
of the merging and annotating steps. (They can be the same group if you
like). At least one group must be selected. Once you've done that, you
can save the project.

For now, the merger group should probably be empty (and therefore a second
group), because merging is currently not implemented for the simple
task.

The 'Type' (Simple, here) is the key part of what makes Clickwork flexible;
it defines the way everything about a project is done. The simple project
is an included example designed to handle simple questions. 


Uploading Data
--------------

Once you have created a project, you can upload data to it. To do so,
go to::

   http://localhost:8000/project/1/upload/

For the simple project, the upload format is simply newline delimited
files; each line in the file becomes a 'question' to the user,
presented according to the templates/tasks/simple_annotator.html 
template. (Currently, this just presents a yes/no with a comments
field.) So to create a file, just create a file with multiple lines
of questions you want to ask (that are yes/no).

You do need to select the project from the dropdown even though it's
in the URL; this is a bug/TODO.

Once you upload, Clickwork will process each line and create a task,
so you can then visit the homepage of the site again to complete the
tasks.

Completing Tasks
----------------

Completing tasks is simple; simply go to the homepage, and click
"Take Next Task". The UI will then give you tasks until you run out,
at which point you will be redirected to /?nomore.

Exporting Data
--------------

Once the tasks are complete, you can export the data by visiting::

  http://localhost:8000/project/1/export/

This will export a zipfile with a -questions file and a -responses.csv
file. (This is configurable by changing the export_task method on
the task.)

This is the entire process to getting the server started, creating
a project, uploading data, tagging it, and exporting it. The next 
step is to create a *real* task type -- one that does the work that you
need to do. 
