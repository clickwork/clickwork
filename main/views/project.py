from django.shortcuts import get_object_or_404, render_to_response
from django.template.loader import get_template
from django.http import HttpResponse
from main.models import Project, ProjectUpload, Task, Response
from django.contrib.auth.decorators import login_required
from django.forms import ModelForm
from main.helpers import get_project_type
from cStringIO import StringIO
import zipfile
from django.conf import settings
from main.views.overview import one_project
from main.wrapper import get, get_or_post, RequestGuts, TemplateResponse, \
    DefaultResponse, AttachmentResponse, ForbiddenResponse, ErrorResponse, ViewResponse
from main.helpers import get_project_type, http_basic_auth
from django.template.loader import get_template
from django.db.models import Count
import django.utils.html
from django.conf import settings

from functools import wraps
def project_owner_required(f):
    """Wraps a function that takes, as its first arguments, either a
    RequestGuts and a Project or a boolean, a RequestGuts, and a
    Project.  Returns a function whose parameters substitute a
    project_id for that Project.  The wrapper is responsible for (a)
    dereferencing the project_id to get the Project object, and (b)
    making sure that the user is either the project administrator or a
    site administrator."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        ## We have to do a little footwork here because we don't know
        ## whether or not the first argument is boolean.
        if isinstance(args[0], bool) and isinstance(args[1], RequestGuts):
            guts_index = 1
            project_index = 2
        elif isinstance(args[0], RequestGuts):
            guts_index = 0
            project_index = 1
        else:
            raise TypeError("Unexpected arguments: %r" % args)
        guts = args[guts_index]
        project = get_object_or_404(Project, pk=args[project_index])
        if guts.user.is_superuser or guts.user == project.admin:
            new_args = list(args)
            new_args[project_index] = project
            return f(*new_args, **kwargs)
        else:
            return ForbiddenResponse("You must be an administrator for the %s project." % project.title)
    return wrapper

class UploadForm(ModelForm):
    class Meta:
        model = ProjectUpload
        fields = ("upload",)

# TODO: Thus far, we have no real hooks for project APIs; this should 
# presumably look up the project task type, and map the 'url' arg into
# the task's APIs.
@get
def project_api(guts, url):
    """Call the project's dispatcher function, based on the URL, and request."""
    pass

@http_basic_auth
@login_required
@get
@project_owner_required
def project_agreement(guts, project):
    ptype = get_project_type(project)
    if not hasattr(ptype, 'test_agreement'):
        return DefaultResponse("Project doesn't support testing agreement.") 

    same_counts = {}
    tasks = project.task_set.filter(completed=True).all()
    for t in tasks:
        responses = t.response_set.all()
        same = ptype.test_agreement(responses)
        same_counts[same] = same_counts.setdefault(same, 0) + 1
    template = get_template('project/agreement.html') 
    print same_counts ## TODO: is this leftover debugging code?
    return TemplateResponse(template, {'counts': same_counts, 'task_count': tasks.count()})

@http_basic_auth
@login_required
@get_or_post
@project_owner_required
def project_upload(get, guts, project):
    """Take an upload, and queue it for running through the task processor.
    
    # TODO: Testing
    # TODO: Return something better than the current Upload complete response. (template)
    # TODO: fix allowing user to select project form a dropdown (project is in the URL).
    # TODO: only allow certain users to upload projects
    """
    ptype = get_project_type(project)
    project = ptype.cast(project)
    if get:
        template = get_template("project/upload_form.html")
        return TemplateResponse(template, {"form": UploadForm()})
    else:
        action = guts.parameters["action"]
        if action == "Upload":
            pu = ProjectUpload(project=project)
            item = UploadForm(guts.parameters, guts.files, instance=pu)
            if item.is_valid():
                item.save()
                if not hasattr(settings, "PROCESS_INLINE") or settings.PROCESS_INLINE:
                    project.handle_input(pu)
                    if project.auto_review:
                        project.add_auto_reviews()
                    pu.complete = True
                    pu.save()
                    message = "Upload complete to project %s, tasks processed" % project.id
                else:
                    message = "Upload complete, queued as %s" % pu.id
                guts.log_info(message)
                return DefaultResponse(message)
            else:
                ## re-present the page with input errors marked
                template = get_template("project/upload_form.html")
                return TemplateResponse(template, {"form": item})
        elif action == "Empty":
            ## NOTE: if subclasses have customized the delete() method,
            ## this bulk-delete will not call it.
            Task.objects.filter(project=project).delete()
            return ViewResponse(one_project, project.id)
        else:
            return ErrorResponse("Bad form", "Action parameter %s not understood" % action)

# TODO: Incremental exports (export what is done today, then export
# what has been finished since that tomorrow) are not implemented.
# at some point, we will want them if we like the current manual
# tagger behavior, but we don't need them yet.

# TODO: We probably want a flag to be able to export partially
# completed tasks, but we may not want them to be exported by
# default.

# TODO: Our current exports are all well-served by using a string
# for each task, and combining them into a zipfile. It's possible this
# is not generic enough.
@http_basic_auth
@login_required
@get
@project_owner_required
def project_export(guts, project):
    """Take in a request and project_id, and export a full set of 
       data using the project's export_task method.

       # TODO: Testing

       Should return a zipfile. Inside the zipfile is one or more 
       files for each Task; the filenames should be like 
       task-id-ExportString, where exportString is a string returned
       from the export_task function.
    """   
    ptype = get_project_type(project)
    project = ptype.cast(project)
    completed_tasks = Task.objects.filter(completed=True, project=project)
    data = []

    buffer = StringIO()
    zip = zipfile.ZipFile(buffer,  "w", zipfile.ZIP_DEFLATED)
    def put(pathname, data):
        if isinstance(data, unicode):
            data = data.encode("utf-8")
        info = zipfile.ZipInfo(pathname)
        info.external_attr = settings.CLICKWORK_EXPORT_FILE_PERMISSIONS << 16L
        zip.writestr(info, data)
    ## a project type can put an export method on its task and/or its project subclass
    try:
        data = project.export()
        for key, val in data.items():
            put("project-%s" % key, val)
    except NotImplementedError:
        pass
    try:
        for task in completed_tasks:
            task = ptype.cast(task)
            task_data = task.export()
            if type(task_data) == dict:
                for key, val in task_data.items():
                    put("task-%s-%s" % (task.id, key), val)
            else:
                put("task-%s" % taskid, task_data)
    except NotImplementedError:
        pass
    zip.close()
    if len(zip.infolist()) == 0:
        return ErrorResponse("Empty export",
                             "Project %s could not be exported; the export file is empty." % \
                                 django.utils.html.escape(repr(project)))
    buffer.seek(0)
    guts.log_info("Exporting project %s to the client" % project.id)
    return AttachmentResponse("project-%s.zip" % project.id,
                              "application/zip", buffer.read())

@http_basic_auth
@login_required
@get
@project_owner_required
def project_stats(guts, project):
    user_response_counts = Response.objects.filter(task__project=project).values("user__username").annotate(Count("id"))
    template = get_template("project/stats.html")
    return TemplateResponse(template, {'user_response_counts': user_response_counts, 'project': project})
