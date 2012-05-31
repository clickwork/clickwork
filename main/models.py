from django import forms
from django.db import models
from django.contrib import admin
from django.contrib.auth.models import Group, User
from django.conf import settings
from django.core.exceptions import ValidationError
from django.template.loader import get_template
import datetime
import inspect
import sys

def abstract():
    """Function to work around (pre-2.6) Python's lack of abstract methods.
    (http://norvig.com/python-iaq.html)"""
    caller = inspect.getouterframes(inspect.currentframe())[1][3]
    raise NotImplementedError(caller + " must be implemented in subclass")

## TODO: After we upgrade to using Django 1.2, appropriate methods
## should be added to these classes to enforce model validation.
## http://docs.djangoproject.com/en/dev/ref/models/instances/?from=olddocs#id1

class Version(models.Model):
    version = models.IntegerField()
    updated = models.DateTimeField(auto_now=True)

class ProjectTag(models.Model):
    """Tags describing projects (there is a many-to-many relationship
    between them)."""
    name = models.CharField(max_length=255, unique=True)

    class Meta:
        ordering = ("name",)

    def __unicode__(self):
        return self.name

class Project(models.Model):
    """The project is the core of the management for Clickwork; it is 
       where tasks are managed. Projects may wish to subclass this if 
       they wish to store custom metadata about the project;
       if they do, they should add a project_class attribute to
       their type.
       """
    class Meta:
        ordering = ('title', )
    def __unicode__(self):
        return u"%s (#%s -- %s)" % (self.title, self.id, self.type)

    #: Project title, used in the project overview page.
    title = models.CharField(max_length=255)
    
    #: Project description, used in the project overview page.
    description = models.TextField()

    #: Identifiers for attributes of a project; useful for filtering.
    tags = models.ManyToManyField(ProjectTag)
    
    #: A list of groups that can annotate/work on this project. 
    annotators  = models.ManyToManyField(Group, related_name="annotator_for") # list of groups
    
    #: A list of groups that can merge this project.
    #: IGNORED FOR AUTO-REVIEW PROJECTS. 
    mergers     = models.ManyToManyField(Group, related_name="merger_for") # list of groups

    #: The project type is one of the TASK_TYPES defined in the 
    #: settings; this describes what kind of project it is.
    type        = models.CharField(max_length=100, choices=((x,x) for x in settings.TASK_TYPES))
    
    #: Currently, projects have a single administrator; the Admin should
    #: eventually have some sort of control over the project.
    #: TODO: Give admin some sort of control over the project.
    admin       = models.ForeignKey(User)
    
    #: The number of annotators/workers that each Task should be given to.
    #: IGNORED FOR AUTO-REVIEW PROJECTS.
    annotator_count = models.IntegerField()

    #: Priority field controls priority of tasks in this project
    #: for users who have access to the project.
    priority    = models.IntegerField(choices=(
        (-1, "Disabled"),
        (0, "Very Low"),
        (1, "Low"),
        (2, "Medium"),
        (3, "High"),
        (4, "Very High")
    ))


    merging_strategy = None # merging still needs consideration

    needs_fresh_eyes = models.BooleanField(default=True)

    auto_review = models.BooleanField(default=False)

    def add_auto_reviews(self):
        """Make sure there is an AutoReview object for every user who
        has permission to annotate this project.  This cannot be run
        until after the project and its associated tasks have been
        saved to the database. If a user is later added to a group
        with annotator permissions, this method will need to be
        re-run."""
        for anno_group in self.annotators.all():
            for task in self.task_set.all():
                for user in anno_group.user_set.all():
                    r, created = AutoReview.objects.get_or_create(user=user,
                                                                  task=task)
                    if created:
                        r.full_clean()
                        r.save()

    @models.permalink
    def get_absolute_url(self):
        return ("main.views.overview.one_project", [str(self.id)])

    def as_dict(self):
        return {"id": self.id,
                "title": self.title,
                "description": self.description,
                "annotators": [unicode(g) for g in self.annotators.all()],
                "mergers": [unicode(m) for m in self.mergers.all()],
                "type": self.type,
                "admin": unicode(self.admin),
                "annotator_count": self.annotator_count,
                "priority": self.priority,
                "needs_fresh_eyes": self.needs_fresh_eyes,
                "tags": [unicode(t) for t in self.tags.all()]}

    def export(self):
        """Returns a dict in which the keys are file names (which will
        be prefixed by \"project-\" in the export zipfile) and the
        values are file contents, either bytestrings or unicode
        objects."""
        raise NotImplementedError("Subclasses must implement either " \
                                      "Project.export() or Task.export()")

###
### Stuff to configure how projects and tags show up on the admin page.
###
class ProjectTagInline(admin.TabularInline):
    model = Project.tags.through
    extra = 0
#    formfield_overrides = { models.ManyToManyField: {"widget": forms.SelectMultiple} }

class ProjectTagAdmin(admin.ModelAdmin):
    inlines = [ProjectTagInline,]

class ProjectAdmin(admin.ModelAdmin):
    inlines = [ProjectTagInline,]
    exclude = ('tags',)

class TaskManager(models.Manager):
    """Customized manager for Task objects."""
    def filtered_projected_and_sorted(self):
        """Return a QuerySet for the tasks that has disabled projects filtered out,
        has an extra wip_count attribute with the number of works in progress for
        each task, and is sorted according to our prioritization rules."""
        ## If the annotate() call comes before the exclude() call,
        ## then generating the SQL query string from the QuerySet
        ## object raises an exception from deep in the bowels of
        ## Django.  I assume this is a Django bug.
        tasks = self.exclude(project__priority=-1)
        tasks = tasks.annotate(wip_count=models.Count("workinprogress"))
        tasks = tasks.order_by("-project__priority", "project__id", "-completed_assignments", "?")
        return tasks

    def can_annotate(self, user):
        """Returns a QuerySet of tasks that the given user can annotate.
        TODO: This QuerySet does NOT filter out the tasks that the user
        HAS ALREADY annotated."""
        excluded_users = list(reduce(lambda s1, s2: s1.union(s2),
                                     [frozenset(map(lambda username:
                                                        User.objects.get(username=username),
                                                    exclusion))
                                      for exclusion in settings.CLICKWORK_KEEP_APART
                                      if user.username in exclusion],
                                     frozenset()) - frozenset([user]))
        groups = user.groups.all()
        tasks = self.filtered_projected_and_sorted()
        tasks = tasks.exclude(response__user__in=excluded_users)
        tasks = tasks.exclude(workinprogress__user__in=excluded_users)
        tasks = tasks.filter(project__annotators__in=groups, # for all tasks where user is an annotator
                             completed = False)
        tasks = tasks.exclude(response__user=user)
        tasks = tasks.filter(project__annotator_count__gt=
                             models.F("wip_count")+models.F("completed_assignments"))
        return tasks

    def can_merge(self, user):
        """Returns a QuerySet of tasks that the given user can merge."""
        groups = user.groups.all()
        ## I wish the QuerySet API had the equivalent of SQL's EXCEPT clause.
        tasks_responded_to = Response.objects.filter(user=user).values("task")
        tasks = self.filtered_projected_and_sorted()
        ## If you take the models.Q() out of the statement below, the method fails:
        ## the query attribute of the QuerySet, which should be a SQL string, is None.
        ## I think this is a Django bug.
        tasks = tasks.exclude(models.Q(project__needs_fresh_eyes=True,
                                       pk__in=tasks_responded_to))
        tasks = tasks.filter(project__mergers__in=groups)
        tasks = tasks.filter(result__isnull=True, wip_count=0, completed=True)
        return tasks

    def next_for(self, user):
        """Return the next task that the user can annotate or merge
        (giving a preference for merging), or None if the user is
        completely caught up."""
        mergeable = self.can_merge(user)
        if mergeable.exists():
            return mergeable[0]
        annotateable = self.can_annotate(user)
        if annotateable.exists():
            return annotateable[0]
        ## if we got here then there is nothing to annotate or merge
        return None

class Task(models.Model):
    """Subclassed by any type that actually wants to store task-specific
    information, most likely, though it's also possible to just use a
    second model with a ForeignKey, if that seems preferable for some
    reason."""

    project = models.ForeignKey(Project)
    completed_assignments = models.IntegerField(default=0)
    completed = models.BooleanField(default=False)

    objects = TaskManager()

    def __unicode__(self):
        return u"task %d of %s" % (self.id, unicode(self.project))

    def summary(self):
        return unicode(self)

    @models.permalink
    def get_absolute_url(self):
        return("main.views.task.task_view", (), {"task_id": str(self.id)})

    @property
    def merge_in_progress(self):
        return self.completed and self.workinprogress_set.count()

    @property
    def merged(self):
        try:
            r = self.result
            return True
        except Result.DoesNotExist:
            return False

    def clean(self):
        super(Task, self).clean()
        if self.completed_assignments == self.project.annotator_count:
            self.completed = True
        ## NOTE: the above code assumes that once a Response is
        ## associated with a Task, it is never taken away.
        if self.merged and not self.completed:
            raise ValidationError("Task is marked \"merged\" but not \"completed\".")

    def as_dict(self):
        return {"id": self.id,
                "project_name": self.project.title,
                "project_id": self.project.id,
                "merged": self.merged,
                "completed": self.completed}

    ## DEPRECATED API (see CW-40)
    @property
    def tagging_template(self):
        """The name of the template to use when presenting this task
        to a user for annotation."""
        abstract()
    @property
    def merging_template(self):
        """The name of the template to use when presenting this task
        to a user for merging."""
        abstract()

    def tagging_template_input(self):
        """A dict that will be translated into a template context when
        annotating this task."""
        abstract()
    def merging_template_input(self):
        """A dict that will be translated into a template context when
        merging this task."""
        abstract()
    def handle_unmerge(self):
        """Undo a merge, if this project has been merged."""
        abstract()

    ## NEW API (see CW-40)
    def template(self):
        """Return the template object that is appropriate for this
        task; it may vary depending on the task's state (incomplete,
        complete, merged, etc.).  Subclasses may override this method
        completely without calling it; this version just falls through
        to calling the appropriate methods of the old API."""
        if self.completed:
            return get_template(self.merging_template)
        else:
            return get_template(self.tagging_template)

    def template_data(self, review=None, auto_review_user=None):
        """Return a dict of information to populate the template with.
        Subclasses that override this method should call it:
            def template_data(self, review=None):
                result = super(TaskSubclass, self).template_data(review)
                ## add other stuff to the result dict
                return result
        """
        ## Try old API
        try:
            if review:
                result = review.review_template_input()
            elif self.completed:
                result = self.merging_template_input()
            else:
                result = self.tagging_template_input()
        except NotImplementedError:
            result = {}
        ## TODO: consistently use either IDs or model objects here
        result["project_id"] = self.project.id
        result["task"] = self
        result["wip_owners"] = [wip.user for wip in self.workinprogress_set.all()]
        if self.completed:
            result["users"] = [x.user for x in self.response_set.all()]
        return result

    ## TODO: there is no handle_response() implementation in the superclass,
    ## although all the subclasses have it.  We should probably do something
    ## about that some day.

    def export(self):
        """Returns a dict, a bytestring, or a unicode object.  In the
        former case, the dict keys are file names (which will be
        prefixed by \"task-<TASKID>-\" in the export zipfile) and the
        values are file contents, either bytestrings or unicode
        objects.  Otherwise, the filename in the export zipfile will
        simply be \"task-<TASKID>\" and the contents will be the
        return value of this method."""
        raise NotImplementedError("Subclasses must implement either " \
                                      "Project.export() or Task.export()")

    def viewable_by(self, user):
        """Indicates whether or not this task can be viewed by the given
        user."""
        if user.is_superuser:
            return True
        if WorkInProgress.objects.filter(task=self, user=user).exists():
            return True
        if self.merged and self.result.user == user:
            return True
        return False

##
## It appears that when a validator is run for a ForeignKey object,
## the argument passed to the validator is the primary key, not the
## model object itself.
##

def is_auto_review(task_id):
    task = Task.objects.get(pk=task_id)
    if not task.project.auto_review:
        raise ValidationError("Task %r is not associated with an auto-review project" % task)

def is_not_auto_review(task_id):
    task = Task.objects.get(pk=task_id)
    if task.project.auto_review:
        raise ValidationError("Task %r is associated with an auto-review project" % task)

class Response(models.Model):
    """Represents one user's work on one task.  Subclassed for specific tasks."""
    user = models.ForeignKey(User)
    task = models.ForeignKey(Task)
    end_time = models.DateTimeField(auto_now_add=True)
    start_time = models.DateTimeField()

    class Meta:
        unique_together = ("user", "task")

    def summary(self):
        """Return a summary of the information in this object; the
        exact semantics may vary by subclass."""
        return None

    def clean(self):
        super(Response, self).clean()
        if self.start_time > (self.end_time or datetime.datetime.now()):
            raise ValidationError("Work on Response cannot end before it begins.")

    def __unicode__(self):
        return u"response by %s to %s" % (unicode(self.user), unicode(self.task))

class Result(models.Model):
    """Represents the merging of several users' work on one task.
    (The 'user' field indicates which user was responsible for the merging.)
    Subclassed for specific tasks."""
    user = models.ForeignKey(User)
    task = models.OneToOneField(Task, validators=[is_not_auto_review])
    end_time = models.DateTimeField(auto_now_add=True)
    start_time = models.DateTimeField()

    def summary(self):
        """Return a summary of the information in this object; the
        exact semantics may vary by subclass."""
        return None

    def __unicode__(self):
        return u"merge by %s of %s" % (unicode(self.user), unicode(self.task))

    def clean(self):
        super(Result, self).clean()
        if self.start_time > (self.end_time or datetime.datetime.now()):
            raise ValidationError("Work on Result cannot end before it begins.")
        if not self.task.completed:
            raise ValidationError("A task cannot be merged before it is annotated.")

class ExpectedResponse(models.Model):
    """For tasks associated with auto-review projects, represents the
    'right answer' that the annotator is supposed to provide."""
    task = models.OneToOneField(Task, validators=[is_auto_review])

class AutoReview(models.Model):
    """Keeps track of which users have seen, or are seeing, which auto-review projects."""
    task = models.ForeignKey(Task, validators=[is_auto_review])
    user = models.ForeignKey(User)
    ## If null, means that the user has not yet been shown this task for review.
    start_time = models.DateTimeField(null=True, blank=True)
    ## If null, means that the user has been shown this task
    ## and has not clicked through yet.
    end_time = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("task", "user")

    def clean(self):
        super(AutoReview, self).clean()
        s1 = frozenset(self.user.groups.all())
        s2 = frozenset(self.task.project.annotators.all())
        if s1.isdisjoint(s2):
            raise ValidationError("User %r does not have permission to annotate %r" % \
                                      (self.user, self.task.project))
        if self.end_time is not None and self.start_time is None:
            raise ValidationError("End time set but start time is null")

class Review(models.Model):
    """When a user demonstrates a lack of understanding of the tagging
       guidelines on a specific task, it is useful for a merger to flag
       the item for the worker to review, showing both the tagger's
       response and the merger's final selection and comment. Reviews
       are created in the task_view/submit handler, and presented to
       the user as additional 'things to complete' by the UI.
    """   
    response = models.ForeignKey(Response)
    comment = models.TextField(blank=True,null=True)
    creation_time = models.DateTimeField(auto_now_add=True)
    complete = models.BooleanField(default=False)

    @property
    def review_template(self):
        """The name of the template to use when presenting this review to the user."""
        abstract()
    def review_template_input(self):
        """A dict that will be translated into a template context when
        reviewing this task."""
        abstract()

class WorkInProgress(models.Model):
    """WorkInProgress tracks the user's current task; used to direct the
    user back to the same task if they lose their browser window,
    etc."""
    task = models.ForeignKey(Task, validators=[is_not_auto_review])
    user = models.ForeignKey(User)

    def __unicode__(self):
        return u"wip for %s working on %s" % (unicode(self.user), unicode(self.task))
    
    #: We store the start_time here, based on when the WIP is 
    #: created, so we can stash it on the Response later.
    start_time = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("task", "user")

class ProjectUpload(models.Model):
    """Track an upload to a project. Uploads are passed to the project
    handle_input function, which will typically read from the uploaded
    file and create tasks.
    
    No specification is made here as to the format of the Upload.
    """

    upload = models.FileField(upload_to="uploads/")
    project = models.ForeignKey(Project)
    timestamp = models.DateTimeField(auto_now=True)
    complete = models.BooleanField(default=False,editable=False)
    error = models.TextField(blank=True)

    def __unicode__(self):
        return u"upload %d to %s at %s" % (self.id, unicode(self.project),
                                           unicode(self.timestamp))

class ProjectType(object):
    """Represents a type of project; hence subclasses of this class
    are associated with subclasses of Project, Task, etc."""

    def cast(self, model):
        """Downcasts a model object from its superclass to its
        concrete class, if the project type has defined the
        appropriate subclass.  If the project type does not match the
        concrete class of the model, an ObjectDoesNotExist exception
        will be raised.  If no subclass is defined in the project
        type, then the original model object will be returned."""
        abstract()

class PageTrack(models.Model):
    """Records when users arrive and depart from pages in the application."""
    user = models.ForeignKey(User, help_text="The user who saw the page.")
    view_name = models.CharField(max_length=100,
                                 help_text="The name of the Django view function associated with the page.")
    view_args = models.CharField(max_length=200,
                                 help_text="The positional arguments passed to the function.")
    view_kwargs = models.CharField(max_length=200,
                                   help_text="The keyword arguments passed to the function.")
    focus_time = models.DateTimeField(help_text="The time the user got focus on the page.")
    blur_time = models.DateTimeField(default=lambda: datetime.datetime.now(),
                                     help_text="The time the user lost focus to the page.")

class Announcement(models.Model):
    """This model is designed to contain site announcements."""
    text = models.TextField()
    enabled = models.BooleanField(default=True)
    date = models.DateTimeField(auto_now=True)

# We load types here, because they load the configured subtypes,
# so that we can have the registered models in subclasses be 
# available as models.
import types

##
## Set up code to receive login/logout signals and log them.  This
## doesn't have much to do with models, but the "Where should this
## code live?" box in
## https://docs.djangoproject.com/en/1.3/topics/signals/ suggests that
## the code be put here, to guarantee that the signal handlers will be
## registered before the signals are actually sent.
##
import logging
from django.dispatch import receiver
from django.contrib.auth.signals import user_logged_in, user_logged_out

logger = logging.getLogger(__name__)

def log_transition(message, **kwargs):
    if kwargs.get("user") is not None:
        username = kwargs["user"].username
    else:
        username = "(anon)"
    if "request" in kwargs and "REMOTE_ADDR" in kwargs["request"].META:
        client_ip = kwargs["request"].META["REMOTE_ADDR"]
    else:
        client_ip = "[NOT_HTTP]"
    logger.info(message, extra={"user": username, "client_ip": client_ip})

@receiver(user_logged_in)
def on_login(sender, **kwargs):
    log_transition("logged in", **kwargs)

@receiver(user_logged_out)
def on_logout(sender, **kwargs):
    log_transition("logged out", **kwargs)
