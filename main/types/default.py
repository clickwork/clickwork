class Default:
    """
    A default task; does nothing, just defines the stubs. 
    """
    #: A string, to be used in the settings.TASK_TYPES 
    #: array and also used in the database to associate
    #: a project with a type.
    name = "default"
    
    #: The Tagging template is the template which is 
    #: used for tagging. The data which is used in the
    #: tagging template is provided by the tagging_template_input
    #: function.
    tagging_template = None

    #: The merging template is the template used for
    #: merge (when task.complete is true). The data which is
    #: used by this template is provided by the merging_template_input
    #: function. Clickwork will automatically add a 'users' template 
    #: variable, with a list of django.auth.contrib.models.User objects
    #: for users who have completed the task.
    merging_template = None
    
    #: The review template is the template used when a merger identifies
    #: that a user should review a given task. The data which is
    #: used by this template is provided by the review_template_input
    #: function. In addition to the template data provided, Clickwork will
    #: add a 'review' template variable, set to True, to indicate that this
    #: is a review template; in some cases, it may make sense to share
    #: a template between merging and reviewing, and simply use the review
    #: flag to add review-specific fields.
    review_template = None

    def handle_input(self, project, input):
        """Given a Project and ProjectUpload object,
           create tasks based on the Project and the Upload."""
        pass
    
    def handle_response(self, guts, task):
        """Given a RequestGuts object, and a Task object,
           generate a Response or Result.

           If the task.completed is true, this should always
           return a Response.

           If the task.completed is not true, this should always
           return a Result.
       """    
    def tagging_template_input(self, task):
        """Given a task, generate a dictionary of data
           to be passed to the tagging template."""
    def merging_template_input(self, task):
        """Given a completed task, generate a dictionary of data
           to be passed to the merging template."""
    def export_task(self, task):
        """Given a task, generate a dictionary of key-value pairs;
           the key should be a component of a filename, which will
           be combined with "task-taskid" to create a filename. The 
           value should be a string representing the desired value
           for this filename.

           The results of this dictionary will be placed inside a 
           zipfile and delivered to the client to download when
           the project is exported.
       """
    def review_template_input(self, review):
        """Generate template data for a review. Reviews have a reference to 
           the response (review.response) object that the user is being 
           requested to review, and the via the response object, the task
           and result can be obtained.

           Generally, a review template input function will do something
           like::
            
             data = self.tagging_template_input(review.response.task)
             data['response'] = {
              'answer': review.response.answer,
              'comment': review.response.comment,
             }
             data['result'] = {
              'answer': review.response.task.result.answer,
              'comment': review.response.task.result.comment,
             }
             data['review_comment'] = review.comment
           
           In this way:
            1. The task tagging input (used to originally present the task
               to the user) is generated via the same template data
            2. The response and result data is included to be displayed
            3. The review comment (created by the merger, directed to the 
               user) is included.
       """        
