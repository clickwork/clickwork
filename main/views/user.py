from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import Group, User
from main.models import Project, Response, Result, Review, Task, ProjectUpload
from main.wrapper import get, DefaultResponse, TemplateResponse, ForbiddenResponse
from main.helpers import get_project_type
from django.template.loader import get_template

@login_required
@get
def recent_results(guts, username):
    """Show a list of recent results."""
    skip = int(guts.parameters.get("skip", 0))
    user = get_object_or_404(User, username=username)
    def contextlet(result):
        ptype = get_project_type(result.task.project)
        return {"result": result,
                "result_summary": ptype.cast(result).summary(),
                "project_type": result.task.project.type,
                "responses": [{"response": response,
                               "response_summary": ptype.cast(response).summary(),
                               "match": ptype.cast(result).summary() == \
                                   ptype.cast(response).summary()}
                              for response in result.task.response_set.all()]}
    if guts.user.is_superuser or guts.user == user:
        recent_results = Result.objects.filter(user=user).order_by("-end_time")[skip:skip+50]
        skips = {"current": "%s - %s" % (skip+1, skip+len(recent_results))}
        if skip >= 50:
            skips['forward'] = (skip - 50) or "0"
        if len(recent_results) == 50:
            skips['backward'] = skip + 50
        template = get_template("recent_results.html")
        template_context = {"results": [contextlet(result) for result in recent_results],
                            "skips": skips, "username": username}
        return TemplateResponse(template, template_context)
    else:
        return ForbiddenResponse("Only the user %s, or an administrator, may see this page." % username)
    

@login_required
@get
def recent_responses(guts, username):
    """Show a list of recent responses"""
    skip = int(guts.parameters.get("skip", 0))
    user = get_object_or_404(User, username=username)
    if guts.user.is_superuser or guts.user == user:
        recent_responses = Response.objects.filter(
            user=User.objects.get(username=username), 
            task__result__id__isnull=False).order_by("-task__result__end_time")[skip:skip+50]
        responses = []    
        for response in recent_responses:
            res = {'response': response}
            res['project_type'] = response.task.project.type
            ptype = get_project_type(response.task.project)
            res['task_summary'] = ptype.cast(response.task).summary()
            res['response_summary'] = ptype.cast(response).summary()
            res['result_summary'] = ptype.cast(response.task.result).summary()
            if res["response_summary"] is not None and res["result_summary"] is not None:
                res['match'] = (res['response_summary'] == res['result_summary'])
            responses.append(res)
        template = get_template("recent_responses.html")
        skips = {}
        skips['current'] = "%s - %s" % (skip+1, skip+len(responses))
        if skip >= 50:
            skips['forward'] = (skip - 50) or "0"
        if len (responses) == 50:
            skips['backward'] = skip + 50
            
        return TemplateResponse(template, 
           {'responses': responses, 'skips': skips, 'username': user.username}
        )   
        
    else:
        return ForbiddenResponse("Only the user %s, or an administrator, may see this page." % username)
