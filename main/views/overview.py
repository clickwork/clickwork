from django.db.models import Count
from django.db import connection
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group, User
from django.shortcuts import get_object_or_404
from django.template.loader import get_template
from main.models import Project, ProjectTag, Response, Result, Review, Task, ProjectUpload
from main.wrapper import get, DefaultResponse, TemplateResponse, ForbiddenResponse

import sys

def all_group_members(groups, cache=None):
    """Takes a list of group objects, and returns the usernames of every
    user who is in at least one of the given groups.  If cache is
    present, it should be a dict mapping group IDs to lists of usernames.  If
    cache is None, this function goes to the database."""
    if cache:
        list_o_sets = [frozenset(cache[g.id]) for g in groups]
    else:
        list_o_sets = [frozenset([u.username for u in g.user_set.all() if u.is_active])
                       for g in groups]
    return sorted(reduce(lambda s1, s2: s1 | s2, list_o_sets, frozenset([])))

def project_info(p, cache=None):
    """Return many things about the given project that we might want to
    pass along to a template for display."""
    return {"id": p.id,
            "title": p.title,
            "url": p.get_absolute_url(),
            "type": p.type,
            "admin": unicode(p.admin),
            "priority": p.get_priority_display(),
            "task_count": p.task_set.count(),
            "annotator_groups": [{"name": g.name, "id": g.id}
                                 for g in p.annotators.all()],
            "annotators": all_group_members(list(p.annotators.all()), cache),
            "merger_groups": [{"name": g.name, "id": g.id}
                              for g in p.mergers.all()],
            "mergers": all_group_members(list(p.mergers.all()), cache),
            "tags": p.tags.all()}

def projects_query_set(filter_tags):
    """Generate a QuerySet object for projects, filtered as necessary according to
    the given tags."""
    projects = Project.objects.filter(priority__gte=0)
    if filter_tags:
        tags = ProjectTag.objects.filter(name__in=filter_tags)
        for tag in tags:
            projects = projects.filter(tags=tag)
    projects = projects.order_by("-id")
    return projects

@login_required
@get
def all_projects(guts):
    """Summarize the status of the active projects whose tags match
    the filters in the query parameter."""
    if guts.user.is_superuser:
        qs = projects_query_set(guts.parameters.getlist("filter"))
        cache = dict([(g.id, [u.username for u in g.user_set.all() if u.is_active])
                      for g in Group.objects.all()])
        result = {"project_list":
                      [project_info(p, cache) for p in qs]}
        template = get_template("overview.html")
        return TemplateResponse(template, result)
    else:
        return ForbiddenResponse("Only administrators can see this page.")

@login_required
@get
def all_projects_brief(guts):
    """Summarize the active projects, whose tags match the filters in
    the query parameter, more succinctly."""
    def extended_dict(project):
        d = project.as_dict()
        d["priority_display"] = project.get_priority_display()
        d["remaining_to_tag"] = project.task_set.filter(completed=False).count()
        d["remaining_to_merge"] = project.task_set.filter(completed=True,
                                                          result__isnull=True).count()
        d["merged"] = project.task_set.filter(completed=True, result__isnull=False).count()
        return d
    if guts.user.is_superuser:
        filter_tags = guts.parameters.getlist("filter")
        qs = projects_query_set(filter_tags)
        data = {"project_list": [extended_dict(p) for p in qs],
                "available_tags": [tag for tag in ProjectTag.objects.all()],
                "selected_tags": filter_tags}
        template = get_template("brief-overview.html")
        return TemplateResponse(template, data)
    else:
        return ForbiddenResponse("Only administrators can see this page.")

@login_required
@get
def one_project(guts, project_id):
    """Summarize information about a single project."""
    project = get_object_or_404(Project, pk=project_id)
    if guts.user.is_superuser or guts.user == project.admin:
        ## Generate assignment counts.  When a project has 5000 or more tasks,
        ## the join-group-and-count operation using the Django QuerySet API
        ## is painfully slow, so we are dropping back to raw SQL here.
        query = """SELECT completed_assignments, COUNT(t.id) AS howmany
                   FROM main_task AS t LEFT JOIN main_result AS r ON (r.task_id = t.id)
                   WHERE project_id = %s AND (r.id IS NULL OR NOT completed)
                   GROUP BY completed_assignments"""
        cursor = connection.cursor()
        cursor.execute(query, [project.id])
        assignments = [{"completed_assignments": completed_assignments,
                        "howmany": howmany}
                       for completed_assignments, howmany in cursor.fetchall()]
        tasks = project.task_set
        needs_merging = tasks.filter(completed=True, result__isnull=True)
        if needs_merging.count():
            assignments.append({'completed_assignments': 'Needs Merging', 'howmany': needs_merging.count()})
        finished = tasks.filter(result__isnull=False)
        if finished.count():
            assignments.append({'completed_assignments': 'Finished', 'howmany': finished.count()})
        
        # Project overview info    
        pi = project_info(project)
        
        # Uploaded files
        uploads = ProjectUpload.objects.filter(project=project)

        # Task info
        MAXIMUM_TASKS_TO_LINK = 1500
        if tasks.count() <= MAXIMUM_TASKS_TO_LINK:
            ti = [{"id": t.id,
                   "url": t.get_absolute_url(),
                   "completed": t.completed,
                   "merged": t.merged}
                  for t in tasks.order_by("id")]
            show_tasks = True
        else:
            ti = None
            show_tasks = False
        template = get_template("project.html")
        return TemplateResponse(template, {"project": pi,
                                           "show_tasks": show_tasks,
                                           "tasks": ti, 
                                           'assignments': assignments, 
                                           'uploads': uploads})
    else:
        return ForbiddenResponse("Only project owners or administrators may see this page.")

@login_required
@get
def all_groups(guts):
    """Summarize information about all the groups in the database."""
    if guts.user.is_superuser:
        groups_info = [{"id": g.id,
                        "name": g.name,
                        "users": [u.username for u in g.user_set.order_by("username")
                                  if u.is_active]}
                       for g in Group.objects.order_by("name")]
        template = get_template("groups.html")
        return TemplateResponse(template, {"groups": groups_info})
    else:
        return ForbiddenResponse("Only administrators can see this page.")

@login_required
@get
def one_group(guts, group_id):
    """Summarize information about one group."""
    if guts.user.is_superuser:
        group = get_object_or_404(Group, pk=group_id)
        users = [u.username for u in group.user_set.order_by("username") if u.is_active]
        emails = [u.email for u in group.user_set.order_by("username") if u.is_active]
        annotates = [{"title": p.title, "id": p.id}
                     for p in group.annotator_for.order_by("title")]
        merges = [{"title": p.title, "id": p.id}
                  for p in group.merger_for.order_by("title")]
        template = get_template("group.html")
        return TemplateResponse(template,
                                {"id": group_id, "name": group.name,
                                 "users": users, "annotates": annotates, "merges": merges, 
                                 "emails": emails})
    else:
        return ForbiddenResponse("Only administrators can see this page.")
        

@login_required
@get
def all_users(guts):
    """Summarize information about all users."""
    if guts.user.is_superuser:
        users = [{"name": u.username,
                  "is_superuser": u.is_superuser,
                  "annotated": u.response_set.count(),
                  "merged": u.result_set.count()}
                 for u in User.objects.order_by("username") if u.is_active]
        template = get_template("users.html")
        return TemplateResponse(template, {"users": users})
    else:
        return ForbiddenResponse("Only administrators can see this page.")

@login_required
@get
def one_user(guts, username):
    """Summarize information about one user."""
    user = get_object_or_404(User, username=username)
    if guts.user.is_superuser or guts.user == user:
        groups = [{"name": g.name, "id": g.id} for g in user.groups.all()]
        recent_responses = [r.task.id for r in
                            Response.objects.filter(user=user).order_by("-end_time")[0:20]]
        recent_results = [r.task.id for r in
                          Result.objects.filter(user=user).order_by("-end_time")[0:20]]
        recent_reviews = [r.id for r in
                          Review.objects.filter(response__user=user).order_by("-creation_time")[0:20]]
        template = get_template("user.html")
        return TemplateResponse(template,
                                {"name": username,
                                 "is_superuser": user.is_superuser,
                                 "groups": groups,
                                 "respondable_task_count": Task.objects.can_annotate(user).count(),
                                 "resolvable_task_count": Task.objects.can_merge(user).count(),
                                 "recent_responses": recent_responses,
                                 "recent_results": recent_results,
                                 "recent_reviews": recent_reviews})
    else:
        return ForbiddenResponse("Only the user %s, or an administrator, may see this page." % username)
