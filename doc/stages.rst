Stages
======

There are three stages that tasks can be in, from the perspective of a user:
needing to be tagged (annotated), needing to be merged, or needing to be 
reviewed. The approximate number of tasks available to the user 
in each stage is listed on the homepage of the clickwork system.

Annotation
----------

The first step of any task is for it to be tagged, or annotated. This
step uses task type's tagging_template_input method to generate a set of
template variables, which are then combined with the type's
tagging_template to generate output.

.. autoattribute:: main.types.default.Default.tagging_template
    :noindex:

.. automethod:: main.types.default.Default.tagging_template_input
    :noindex:


Merging
-------

Merging is the second stage of a task. (Note that merging is not 
required; if you do not wish to merge, you can simply create a project
with no merging_template or merging_template_input.)

In general, merging templates should provide a reviewer:
 * The same information that the annotator originally saw. Oftentimes,
   it may work best to simply start with the same template data as is
   returned by the tagging_template_input function, and append 
   user responses as additional data.
 * The responses provided by other users to the task.

In addition, the merging template will get a list of User objects
(passed in the 'users' template variable) that worked on the task.
If the POST data with the merge includes a 'review_user' value,
it is assumed to be a list of user-ids who should review the merged
value. Additionally, you can add a "comment_<userid>" value in the POST
as well: this will cause the comment to be stored alongside the review
for use in the review template.

Generally, HTML like the following:

.. code-block:: html


    {% if users %}
    <div>
    Ask the following users to review the merged result and response:
    <ul>
    {% for user in users %}
      <li><input name="review_user" type="checkbox" value="{{user.id}}" />
    {{user.username}} Comment: <input type="text" name="comment_{{user.id}}"
    size="50" /></li>
    {% endfor %}
    </ul>
    </div>
    {% endif %}

can be used to lay out a form for mergers to select users who should
review the merge results.

Reviewing
---------

If, when creating a merge template, you include the review_user and
comment_<userid> fields, then a Review object is created.

.. autoclass:: main.models.Review
    :members:
    :noindex:


Users are forced, by the next_task handler, to review anything marked
as review before they can do any further work. (This will interrupt the
flow of the tagging user, but since the review will generally be created
because the tagger did not have sufficient understanding of the task,
this is often desirable.) Reviews will use the review_template_input
function to generate template data:

.. automethod:: main.types.default.Default.review_template_input
    :noindex:

.. autoattribute:: main.types.default.Default.review_template
    :noindex:


