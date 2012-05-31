from main.models import Task, WorkInProgress
from main.types import type_list
from django.contrib.auth.models import User
from django.conf import settings

import sys

def get_project_type(project):
    if type_list.has_key(project.type):
        return type_list[project.type]
    raise Exception("Project %s has type %s, which is not in: %s" % (project.id, project.type, type_list.keys()))    
