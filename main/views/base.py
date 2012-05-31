from django import forms
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.urlresolvers import resolve, reverse
from django.http import HttpResponseRedirect
from django.shortcuts import render_to_response
from django.template.loader import get_template
from main.models import Task, WorkInProgress, Response, Result, Review, AutoReview, PageTrack, Announcement
from main.wrapper import get, get_or_post, TemplateResponse, ViewResponse, RefererResponse, \
    ForbiddenResponse, RequestGuts
from urlparse import urlparse
import datetime
import sys
from django.db import transaction

import main.views.overview
import main.views.project
import main.views.timesheets
import main.views.task
import user_management.views

###
### WARNING: For efficiency, the list of links displayed on the main
### page is cached in the Django session object (guts.session).  If
### you are debugging this page in a way that affects those links, THE
### CACHED LIST WILL NOT BE CLEARED AUTOMATICALLY.
###
@login_required
@get
def home(guts):
    """Manage the display of the homepage. Currently returns a count for
       the number of resolvable tasks.
       
       Template data should include the counts of tasks the user can
       annotate or merge.
       """
    site_messages = Announcement.objects.filter(enabled=True)
    respondable_tasks = Task.objects.can_annotate(guts.user)
    resolvable_tasks = Task.objects.can_merge(guts.user)
    recent_responses = Response.objects.filter(user=guts.user).order_by('-end_time')[0:5]
    recent_results = Result.objects.filter(user=guts.user).order_by('-end_time')[0:5]
    reviews = Review.objects.filter(complete=False, response__user=guts.user)
    if "visitable_pages" not in guts.session:
        guts.session["visitable_pages"] = visitable(guts.user)
    template = get_template("home.html")
    return TemplateResponse(template, {'respondable_tasks': respondable_tasks,
                                       'respondable_task_count': respondable_tasks.count(),
                                       'resolvable_tasks': resolvable_tasks,
                                       'resolvable_task_count': resolvable_tasks.count(),
                                       'recent_responses': recent_responses,
                                       'recent_results': recent_results,
                                       'reviews': reviews,
                                       "pages": guts.session["visitable_pages"],
                                       "messages": site_messages})



def visitable(user):
    """Gather information about which pages this user can visit by
    filtering the PAGES variable."""
    guts = RequestGuts(user=user)
    def reverse_if_visitable(view_function):
        try:
        	seed = view_function.dispatcher["GET"](guts)
        	if isinstance(seed, ForbiddenResponse):
        	    return None
        	else:
        	    return reverse(view_function)
        except Exception, E:
            return None # If a view throws an exception because it's not configured, don't throw errors on the homepage
    visitable_pages = [{"category": category,
                        "url": reverse_if_visitable(view_function),
                        "description": description}
                       for category, view_function, description in PAGES
                       if reverse_if_visitable(view_function)]
    ## we shouldn't do the "try visiting this page" hack for the next_task page,
    ## since (a) this should always be accessible, and (b) visiting the page will
    ## cause a WIP to be assigned to the user as a side effect.
    visitable_pages.insert(0, {"category": "Tasks",
                               "url": reverse(next_task),
                               "description": "Take next task"})
    ## hack to include the admin site
    if user.is_staff:
        visitable_pages.append({"category": "Miscellaneous",
                                "url": "/admin/",
                                "description": "Administer the site"})
    visitable_pages.append({
        "category":"Overviews", 
        "url": "/user/%s/responses/" % guts.user.username,
        "description": "Recently Merged Responses"})
    return visitable_pages


@get
def about(guts):
    """Manage the display of the homepage"""
    template = get_template("about.html")
    return TemplateResponse(template, {})

@transaction.commit_on_success
@login_required
@get
def next_task(guts):
    """Get the next task for a user, and redirect.
    
    It is possible this belongs with the task views.

    # TODO: Testing
    
    The input request should have a logged in user. The result
    should be:
     * If the user has nothing to do, redirect to the home page.
     * If the user has a pending review, redirect to that review's page.
     * If the user has a task in an auto-review project to look at,
       redirect to that page.
     * If the user either has a WorkInProgress or there is a task
       available for them to work on, a redirect to that task's page.
     * If a WorkInProgress exists, the .start_time property of the
       WIP should be updated to the current time.
     * If no WIP exists, one should be created with the next available
       task and the current logged in user.
    """
    review = Review.objects.filter(response__user=guts.user, complete=False)
    if review.count():
        return ViewResponse(main.views.task.next_review)

    auto_review_pending = AutoReview.objects.filter(user=guts.user,
                                                    start_time__isnull=False,
                                                    end_time__isnull=True)
    if auto_review_pending.exists():
        return ViewResponse(main.views.task.task_view,
                            auto_review_pending[0].task.id)
    new_auto_reviews = AutoReview.objects.filter(
        user=guts.user, task__project__priority__gte=0,
        start_time__isnull=True, end_time__isnull=True).order_by("-task__project__priority")
    if new_auto_reviews.exists():
        auto_review = new_auto_reviews[0]
        auto_review.start_time = datetime.datetime.now()
        auto_review.full_clean()
        auto_review.save()
        return ViewResponse(main.views.task.task_view,
                            auto_review.task.id)

    wip = None
    wips = WorkInProgress.objects.filter(user=guts.user)
    if wips.count():
        wip = wips[0]
        wip.start_time = datetime.datetime.now()
        wip.full_clean()
        wip.save()
    else:
        task = Task.objects.next_for(guts.user)
        if task:
            wip = WorkInProgress(user=guts.user, task=task)
            wip.full_clean()
            wip.save()
    if wip:
        return ViewResponse(main.views.task.task_view, wip.task.id)
    else:
        return ViewResponse(home)

## TODO: Needs testing.
## TODO: This code assumes that each user may only have one WIP.
##       The model should enforce that, or the view and template
##       need to be adapted to other possibilities.
## TODO: What if the user goes to this page and has no WIPs?
@login_required
@get_or_post
def abandon_wip(get, guts):
    """A view to abandon a WIP. When GETting this page, the user sees
    the \"are you sure?\" page.  When POSTing, the first WIP that the
    user has is deleted.
    """
    if get:
        wips = WorkInProgress.objects.filter(user=guts.user)
        template = get_template("abandon_wip.html")
        return TemplateResponse(template, {'wips':wips})
    else:
        wips = WorkInProgress.objects.filter(user=guts.user)
        if wips.count():
            wip = wips[0]
            wip.delete()
            return ViewResponse(home)
        else: 
            template = get_template("abandon_wip.html")
            return TemplateResponse(template, {"wips": wips})

class PageTrackForm(forms.Form):
    user = forms.ModelChoiceField(queryset=User.objects.order_by("username"))
    url = forms.URLField(max_length=100)
    focus_time = forms.DateTimeField()
    blur_time = forms.DateTimeField(required=False)

from django.template import Template
page_track_template = Template("""{% extends "base.html" %}
{% block title %}Page Track Test (ADMINS ONLY!){% endblock %}
{% block heading %}Page Track Test (ADMINS ONLY!){% endblock %}
{% block content %}
{% if pt %}
<p><b>PageTrack object {{ pt.id }} successfully entered.</b></p>
{% endif %}
<form action="#" method="POST">
  {{ form.as_p }}
  <input type="submit" value="Submit fake page-tracking info" />
</form>
{% endblock %}""")

@login_required
@get_or_post
def track_page_visit(get, guts):
    if get:
        form = PageTrackForm()
        return TemplateResponse(page_track_template, {"form": form})
    else:
        if guts.user.is_superuser:
            form = PageTrackForm(guts.parameters)
            if form.is_valid():
                url = form.cleaned_data["url"]
                view, view_args, view_kwargs = resolve(urlparse(url).path)
                print >>sys.stderr, repr(form.cleaned_data)
                pt = PageTrack(user=form.cleaned_data["user"],
                               view_name=view.__name__,
                               view_args=repr(view_args),
                               view_kwargs=repr(view_kwargs),
                               focus_time=form.cleaned_data["focus_time"])
                if "blur_time" in form.cleaned_data:
                    pt.blur_time = form.cleaned_data["blur_time"]
                pt.full_clean()
                pt.save()
                new_form = PageTrackForm()
                return TemplateResponse(page_track_template, {"form": new_form,
                                                              "pt": pt})
            else:
                return TemplateResponse(page_track_template, {"form": form})
        else:
            return ForbiddenResponse("Only superusers may use this form.")

### These are the pages that might be shown in the sitemap.
### They must all be accessible to at least some users without parameters or URL variations.
PAGES = (("Tasks", abandon_wip, "Abandon the work in progress"),
         ("Accounts", user_management.views.change_password, "Change your password"),
         ("Accounts", main.views.timesheets.timesheet, "Generate (estimated) timesheets"),
         ("Overviews", main.views.task.wip_review, "See works in progress"),
         ("Overviews", main.views.overview.all_projects_brief, "See projects"),
         ("Overviews", main.views.overview.all_groups, "See groups"),
         ("Overviews", main.views.overview.all_users, "See users"),
         )
