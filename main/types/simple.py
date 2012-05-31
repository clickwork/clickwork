from main.models import Project, Task, Response, Result, ProjectType
from django.db import models

import csv
from cStringIO import StringIO

class SimpleProject(Project):
    class Meta:
        proxy = True

    def handle_input(self, input):
        """Given ProjectUpload object, create tasks based on it."""
        for line in input.upload:
            line = line.rstrip()
            task = SimpleTask(question=line, project=self)
            task.full_clean()
            task.save()

class SimpleTask(Task):
    """A basic task, with just a single textfield for
       input."""
    class Meta:
        app_label = "main"
    question = models.TextField()
    
    #: The Tagging template is the template which is 
    #: used for tagging. The data which is used in the
    #: tagging template is provided by the tagging_template_input
    #: function.
    @property
    def tagging_template(self):
        return "tasks/simple_annotator.html"
    @property
    def merging_template(self):
        return "tasks/simple_merger.html"
        
    def tagging_template_input(self):
        """Given a task, generate a dictionary of data
           to be passed to the tagging template."""
        return {'question': self.question}   

    def merging_template_input(self):
        """Given a completed task, generate a dictionary of data
           to be passed to the merging template."""
        data = self.tagging_template_input()
        data["responses"] = [{"answer": r.simpleresponse.answer, "comment": r.simpleresponse.comment}
                             for r in self.response_set.all()]
        return data
    
    def handle_response(self, guts, **kwargs):
        """Generate the appropriate subclass of Response or Result,
           given a RequestGuts object and a dict containing whatever
           parameters the Request or Response superclass needs to know
           about.  The caller is responsible for populating that dict,
           and one key of that dict has to be 'task'.  This function
           is responsible for creating an instance of the subclass and
           saving it to the DB.
        """
        if kwargs["task"].completed:
            res = SimpleResult(answer=guts.parameters['answer'], comment=guts.parameters['comment'], **kwargs)
        else:
            res = SimpleResponse(answer=guts.parameters['answer'], comment=guts.parameters['comment'], **kwargs)
        res.full_clean()
        res.save()
    
    def export(self):
        """Generate a dictionary of key-value pairs for this task;
           the key should be a component of a filename, which will
           be combined with "task-taskid" to create a filename. The 
           value should be a string representing the desired value
           for this filename.

           The results of this dictionary will be placed inside a 
           zipfile and delivered to the client to download when
           the project is exported.
        """
        input_string = StringIO()
        input_string.write(self.question.encode("utf-8"))

        response_string = StringIO()
        writer = csv.writer(response_string)
        writer.writerow(['user', 'answer', 'comment'])
        for response in self.response_set.all():
            simple_res = response.simpleresponse
            writer.writerow([response.user.username, simple_res.answer, simple_res.comment])
        
        input_string.seek(0)
        response_string.seek(0)

        return {'question.txt': input_string.read(), 'responses.csv': response_string.read()}   

class SimpleResponse(Response):
    """Response to simple question; includes fields for
       answer (char) and comment (textarea)"""
    class Meta:
        app_label = "main"
    answer = models.CharField(max_length=255)
    comment = models.TextField()

class SimpleResult(Result):
    """Merged result for simple responses; answer + comment"""
    class Meta:
        app_label = "main"
    answer = models.CharField(max_length=255)
    comment = models.TextField()

models.loading.register_models("main", 
    SimpleTask,
    SimpleResponse,
    SimpleResult)

class Simple(ProjectType):
    """
    A simple task; takes in a file, and presents the rows
    as questions with a single response. 
    """

    @property
    def project(self):
        return SimpleProject

    #: A string, to be used in the settings.TASK_TYPES 
    #: array and also used in the database to associate
    #: a project with a type.
    name = "simple"

    def cast(self, model):
        if isinstance(model, Task):
            return model.simpletask
        elif isinstance(model, Project):
            return SimpleProject.objects.get(pk=model.id)
        else:
            return model
                
def get_type():
    """Return the type for the simple project."""
    return Simple()
