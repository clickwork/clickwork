Frequent Problems
=================

app_label
---------

When using custom models, omitting::

      class Meta:
          app_label = "main" # required for django to not blow up

will cause Django to throw an unclear error message like::

  File "/Library/Python/2.6/site-packages/Django-1.1.2-py2.6.egg/django/contrib/contenttypes/management.py", line 20, in update_contenttypes
      content_types.remove(ct)
      ValueError: list.remove(x): x not in list

If you are getting this error message, ensure that your custom 
models have an app_label defined in the Meta class.


Unavailable Custom Models
-------------------------

If your custom models do not seem to be available in syncdb/sqlall
commands:

 1. Ensure that you have registered the models::

   models.loading.register_models("main", DefaultTask)

 2. Ensure that the task type is configured in the TASK_TYPES
    in your local_settings.py file.

    
