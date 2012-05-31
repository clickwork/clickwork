Types
=====

All projects in Clickwork have a 'type'; this is the core component 
behind the extensibility of Clickwork. Basically, it should be possible
to write a completely customized UI and data collection pieces for
Clickwork without doing anything more than using a custom-built task.

A task has the following properties:

.. autoclass:: main.types.default.Default 
    :members:

In addition, it is possible to define additional models that subclass the
main models (Like Task, etc.) To do so, you simply define your model as
a subclass of Task, and then register it with Django.

::

    from django.db import models
    from main.models import Task
    class DefaultTask(Task):
        class Meta:
            app_label = "main" # required for django to not blow up
        input = models.CharField(max_length=255)
        more_input = models.IntegerField()
    models.loading.register_models("main", DefaultTask)

One additional thing that tasks must do is have a get_type function
defined in the module that returns an instance of the type:

::

    def get_task():
        return DefaultTask()

In general, the process for data is:

 1. handle_input: This function takes in the uploaded file, and turns
    it into tasks by creating instances of the Type's sub-class of
    Task.
 2. Once the tasks are created, Clickwork will select the tasks to
    pass to users; one this is done, it will call tagging_template_input,
    passing the task as an argument, to allow this function to generate
    potential template output to use to populate the template.
 3. When the user finishes tagging, their POST to the server is passed to 
    the handle_response function of the task, which must create and return
    a Response object.
 4. Once the tasks have been handed to a number of users equal to the
    number of annotators, Clickwork will try to hand the task to a 
    merger, passing the task id to the merging_template_input function
    to generate template variables, then combining that with the
    merging_template property to return an HTML page. 
 5. Similar to before, the handle_submit function takes the returned 
    data, and this time, expects a Result object.
 6. At any point in the process, a user can call the /export/ URL,
    and dump out the current state of the project, which causes
    Clickwork to pass each task to the export_task function, building
    up a zipfile of responses.

Each of these steps is controlled by the tasks, which are written
by people deploying the Clickwork system.
