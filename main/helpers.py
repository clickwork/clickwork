from main.models import Task, WorkInProgress
from main.types import type_list
from django.contrib.auth.models import User
from django.conf import settings

import sys
from functools import wraps

def http_basic_auth(func):
    @wraps(func)
    def _decorator(request, *args, **kwargs):
        from django.contrib.auth import authenticate, login
        if request.META.has_key('HTTP_AUTHORIZATION'):
            authmeth, auth = request.META['HTTP_AUTHORIZATION'].split(' ', 1)
            if authmeth.lower() == 'basic':
                auth = auth.strip().decode('base64')
                username, password = auth.split(':', 1)
                user = authenticate(username=username, password=password)
                if user:
                    login(request, user)
        return func(request, *args, **kwargs)
    return _decorator


def get_project_type(project):
    if type_list.has_key(project.type):
        return type_list[project.type]
    raise Exception("Project %s has type %s, which is not in: %s" % (project.id, project.type, type_list.keys()))    
