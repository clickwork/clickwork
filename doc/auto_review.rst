Notes on auto-review projects
=============================

Auto-review is a new feature, available on certain types of clickwork
projects.  When a user is listed as an annotator for an auto-review
project, he or she will see auto-review tasks before any other kind of
tasks, except for reviews that have been requested by a merger.  The
user fills out the task submission form as usual, and upon submitting
the form, immediately seeing a comparison between his or her answers
and the predetermined correct answers.

From the administrator's point of view, creating an auto-review
project is slightly different from creating a regular project, because
those "correct answers" must be provided at task-upload time, not
given by mergers.  The way to provide this information differs,
depending on what type of project is being created.

Uploading data to vitality2 auto-review projects
------------------------------------------------

The file format for a vitality2 auto-review project is the same as it
is for a regular vitality2 project, except it has one additional
column.  This column must have (on one line) a JSON-formatted object
describing the correct answer.  Here is an example, taken from the
``test-auto-review.tsv`` file: ::

   {"understandable": true, "comment": "auto-review!", "places": [{"address": "Earth", "scope": "local", "lat": 0.0, "lon": 0.0, "url": "http://example.com/"}]}

The JSON format allows one to define an auto-review task as having
multiple places associated with it.

Uploading data to vital_assisted_rating (VAR) auto-review projects
------------------------------------------------------------------

For a normal VAR project, the file uploaded to populate the project is
ignored (although it must be non-empty); all the information about the
VAR project is taken from the associated vitality2 project.  For
auto-review VAR projects, this file must be a JSON document, with the
following format: ::

  [{"vitality": <vitality2 task id>,
    "ovi_xml": <xml document in the same format that Ovi Maps uses>,
    "responses": [{"rating": <"vital", "useful", etc.>,
                   "comment": ...,
		   "other_vitals_exist": ...,
                   "other_vital_comment": ...,
		   "other_vital_type": ...,
		   "usp": <ID of the corresponding UserSubmittedPlace object>},
		 ]},
   ...]

In the outer list, there is one object for every vitality2 task in the
referred-to project.  In the inner lists, the values of the
``responses`` keys, there is one object for every ``<item/>`` element
in the associated XML file (and they must be in the same order).

Adding auto-review functionality to other project types
-------------------------------------------------------

If you as a developer would like to make other kinds of projects
capable of auto-review, you need to take the following steps:

1. Make an ``ExpectedResponse`` subclass for that project type.

2. Modify your project type's ``Project`` subclass so that its
``handle_input`` method checks to see if ``self`` is an auto-review
project, and if so, instantiates the ``ExpectedResponse`` based on
the extra information in the input.

3. Allow your ``Task`` subclass's ``template_data`` method to accept
an optional ``auto_review_user`` keyword argument.  If this argument
is not set, then the method should return the same page as usual (the
user is seeing the task for the first time and needs to annotate it).
If it is set, then the method should look up the ``Response`` object
associated with that user and display the same kind of page that would
be shown for a review (with the ``ExpectedResponse`` object in place
of the ``Result``).

4. Add a section to this file that tells administrators how to upload
tasks to an auto-review project of your type.
