from django.shortcuts import get_object_or_404
from main.models import Project, Task, WorkInProgress, Response, Result, User, Review, AutoReview
from main.types import type_list
from django.contrib.auth.decorators import login_required
from main.helpers import get_project_type
from main.wrapper import get, get_or_post, TemplateResponse, ViewResponse, ForbiddenResponse, DefaultResponse, ErrorResponse
from django.template import Context, Template
from django.template.loader import get_template
from django.utils.datastructures import MultiValueDictKeyError
import datetime
import sys
import traceback

@login_required
@get_or_post
def task_view(get, guts, task_id):
    """View a given task ID or submit a response to it; in either
    case, this should dispatch appropriately based on the task's
    type."""
    import main.views.base
    task = Task.objects.get(pk=task_id)
    project_type = type_list[task.project.type]
    task = project_type.cast(task)
    try:
        wip = WorkInProgress.objects.get(task=task, user=guts.user)
    except WorkInProgress.DoesNotExist:
        if task.project.auto_review:
            try:
                ## Tasks in auto-review projects have a kludgey workflow:
                ## the task is responsible for noticing that it is in an
                ## auto-review project and adjusting the output of template()
                ## and template_data accordingly.
                ## When GETting the page, if a Response object already exists, then
                ## the output should be appropriate for displaying a review.
                auto_review = AutoReview.objects.get(task=task, user=guts.user)
                if get:
                    ## If the Task subclass has not been retrofitted to handle
                    ## auto-review projects, then this line will throw an exception
                    ## "TypeError: ... unexpected keyword argument 'auto_review_user'"
                    return TemplateResponse(task.template(),
                                            task.template_data(auto_review_user=guts.user))
                else:
                    ## NOTE: does the downcasting of task screw this query up?
                    response_query = Response.objects.filter(user=guts.user,
                                                             task=task)
                    if not response_query.exists():
                        ## No response?  Ask the task to make one!
                        kwargs = {"user": guts.user,
                                  "task": task,
                                  "start_time": auto_review.start_time}
                        task.handle_response(guts, **kwargs)
                        ## (Note that this code path does NOT update the task's
                        ## completed_assignments field, because auto-review projects
                        ## do not have a limit on how many responses they can have.)
                        ##
                        ## And then GET this page again, so the user can see the review.
                        return ViewResponse(task_view, task_id)
                    else:
                        ## The user must have clicked the "I read this review" button.
                        auto_review.end_time = datetime.datetime.now()
                        auto_review.full_clean()
                        auto_review.save()
                        return ViewResponse(main.views.base.next_task)
            except AutoReview.DoesNotExist:
                ## fall through to the case below, since an admin is allowed to
                ## look at someone else's auto-review
                pass
        ## an admin can look at any task, but not even an admin
        ## can submit a response or result to a task without getting a WIP first
        if not (task.viewable_by(guts.user) and get):
            return ForbiddenResponse(u"You are not allowed to view %s" % unicode(task))
    if get:
        return TemplateResponse(task.template(), task.template_data())
    else:
        ## TODO: if we successfully make handle_response a method of the task,
        ## then we don't have to pass the task in kwargs
        kwargs = {"user": guts.user,
                  "task": task,
                  "start_time": wip.start_time}
        try:
            task.handle_response(guts, **kwargs)
            if task.completed:
                if 'review_user' in guts.parameters:
                    users = guts.parameters.getlist('review_user')
                    for user in users:
                        user_obj = User.objects.get(pk=user)
                        comment = guts.parameters.get("comment_%s" % user, "")
                        rev = Review(response=task.response_set.get(user=user_obj), comment=comment)
                        rev.full_clean()
                        rev.save()
            else:
                task.completed_assignments = task.completed_assignments + 1
                task.full_clean()
                task.save()
            wip.delete()
            if 'stop_working' in guts.parameters:
                return ViewResponse(main.views.base.home)
            else:
                return ViewResponse(main.views.base.next_task)
        except MultiValueDictKeyError:
            ## translate the MultiValueDict into a list of (key, list) pairs
            params = guts.parameters.lists()
            exc_type, exc_value, exc_traceback = sys.exc_info()
            tb_info = traceback.extract_tb(exc_traceback)
            template = get_template("parameter-error-in-task.html")
            context = {"task": str(task), "params": params,
                       "exc_value": exc_value, "traceback": tb_info}
            guts.log_error("Bad form? " + repr(context))
            return TemplateResponse(template, context, status=500)

@login_required
@get
def next_review(guts):
    """If a user has an outstanding task to review, redirect them to it.
       Otherwise, redirect them to the homepage."""
    import main.views.base
    review = Review.objects.filter(response__user=guts.user, complete=False)
    if review.count():
        review = review[0]
        return ViewResponse(task_review, review.id)
    return ViewResponse(main.views.base.home)

@login_required
@get_or_post
def task_adhoc_review(get, guts):
    if get:
        response_id = guts.parameters['response']
        response = Response.objects.get(pk=response_id)
        reviews = Review.objects.filter(response=response)
        if reviews.count() == 1:
            review = reviews[0]
        else:
            review = Review(response=response, comment="")
        task = response.task
        result = task.result
        # Tagger or merger can both view, as well as super-user
        if (response.user != guts.user) and not (guts.user.is_superuser) and (result.user != guts.user):
            return ForbiddenResponse("You are not authorized to see this review.")
        project_type = get_project_type(task.project)
        task = project_type.cast(task)
        try:
            template = get_template(review.review_template)
        except NotImplementedError:
            template = task.template()
        template_data = task.template_data(review=review)
        return TemplateResponse(template, template_data)
    else:
        return ViewResponse(next_review)

@login_required
@get_or_post
def task_review(get, guts, review_id):
    """Present an interface to request the user to review 
       a given task."""
    review = get_object_or_404(Review, pk=review_id)
    response = review.response
    ## NOTE: an earlier version of this code would throw a Review.DoesNotExist exception
    ## if the Review object with the right id and user had complete=True.  I don't see
    ## the harm in re-reviewing so I am not checking for that here.
    if (response.user != guts.user) and not (guts.user.is_superuser or get):
        return ForbiddenResponse("You are not authorized to see this review.")
    if get:
        task = response.task
        project_type = get_project_type(task.project)
        task = project_type.cast(task)
        try:
            template = get_template(review.review_template)
        except NotImplementedError:
            template = task.template()
        template_data = task.template_data(review=review)
        return TemplateResponse(template, template_data)
    else:
        review.complete = True
        review.full_clean()
        review.save()
        return ViewResponse(next_review)

@login_required
@get_or_post
def unmerge(get, guts, task_id):
    """Given a task that has already been merged, undo the merge, give
    the user a WIP for re-merging it, and redirect to the page for
    handling that WIP.  This operation may not be supported for all
    project types, and may only be executed by a superuser."""
    if guts.user.is_superuser:
        if not get:
            task = get_object_or_404(Task, pk=task_id)
            project_type = get_project_type(task.project)
            task = project_type.cast(task)
            task.handle_unmerge()
            wip = WorkInProgress(user=guts.user, task=task)
            wip.full_clean()
            wip.save()
        return ViewResponse(task_view, task_id)
    else:
        return ForbiddenResponse("Only superusers may perform this operation.")

@login_required
@get_or_post
def wip_review(get, guts):
    if guts.user.is_superuser:
        wips = WorkInProgress.objects.all()
    elif Project.objects.filter(admin=guts.user).count():
        wips = WorkInProgress.objects.filter(task__project__admin=guts.user)
    else:
        return ForbiddenResponse("Only project administrators and superusers may see this page.")
    if get:
        wip_list = [{"id": wip.id,
                     "user": wip.user.username,
                     "task_id": wip.task.id,
                     "task_url": wip.task.get_absolute_url(),
                     "project_id": wip.task.project.id,
                     "project_name": wip.task.project.title,
                     "project_url": wip.task.project.get_absolute_url(),
                     "start_time": wip.start_time}
                    for wip in wips.order_by("-start_time")]
        template_data = {"wips": wip_list}
        template = get_template("wip-review.html")
        return TemplateResponse(template, template_data)
    else:
        try:
            wips_to_delete = [wips.get(pk=pk) for pk
                              in guts.parameters.getlist("wips_to_delete")]
            for wip in wips_to_delete:
                wip.delete()
            return ViewResponse(wip_review)
        except WorkInProgress.DoesNotExist:
            return ForbiddenResponse("You can only delete a project " \
                                         "that you are an admin for.")
