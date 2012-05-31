from django.db import models
from main.models import Task, Response, Project, ProjectType
import csv
from cStringIO import StringIO

class CategorizationProject(Project):
    def handle_input(self, input):
        f = StringIO(input.encode("utf-8"))
        r = csv.reader(f)
        for row in r:
            ci = []
            ct = CategorizationTask(project=self)
            ct.full_clean()
            ct.save()
            for q in row:
                c = CategorizationInput(query_string=q)
                c.full_clean()
                c.save()
                ci.append(c)
                ct.queries.add(c)
            ct.full_clean()
            ct.save()

class CategorizationInput(models.Model):   
    class Meta:
        app_label = "main"
    query_string = models.CharField(max_length=255)

class CategorizationTask(Task):
    class Meta:
        app_label = "main"
    queries = models.ManyToManyField(CategorizationInput) 

    @property
    def tagging_template(self):
        return "tasks/categorization_annotator.html"

    def tagging_template_input(self):
        queries = []
        i = 1
        for q in self.queries.all():
            queries.append({'id': i, 'query': q.query_string})
            i += 1
        return {'queries': queries}

    def handle_response(self, guts, **kwargs):
        response = CategorizationResponse(category="", comment="", order="") 
        return response

class CategorizationResponse(Response):
     class Meta:
        app_label = "main"
     category = models.CharField(max_length=255)
     comment = models.TextField()
     order = models.IntegerField()

models.loading.register_models("main", CategorizationInput)
models.loading.register_models("main", CategorizationTask)
models.loading.register_models("main", CategorizationResponse)

class Categorization(ProjectType):
    # A string, must be unique across the install
    name = "categorization"

    def cast(self, model):
        if isinstance(model, Task):
            return model.categorizationtask
        elif isinstance(model, Project):
            return model.categorizationproject
        else:
            return model

def get_type():
    return Categorization()
