"""Classes for managing the view that shows how much time users have spent on tagging and merging.
"""

import datetime
import sys
from main.models import Response, Result
from main.wrapper import get, DefaultResponse, ErrorResponse, ForbiddenResponse, TemplateResponse
from django import forms
from django.contrib.auth.models import User, Group
from django.contrib.auth.decorators import login_required
from django.template.loader import get_template

### TODO: Replace usages of "tagging"/"merging" and "week"/"month" throughout
### with type-safe enums.

class TimeBlockSpec(object):
    """Describes what kind of TimeBlock objects should be used in a
    particular timesheet report.  The 'resolution' attribute indicates
    whether we are working on a scale of weeks or months; the
    'periods' attribute indicates how many weeks or months back we are
    looking; the 'latest_block_contains' attribute is a datetime
    object within the latest TimeBlock object that this instance will
    emit.  Iteration through a TimeBlockSpec object will 

    >>> import datetime
    >>> tbs1 = TimeBlockSpec("month", 1, datetime.datetime(2010, 1, 1))
    >>> [str(block) for block in tbs1]
    ['month 12 of 2009', 'month 1 of 2010']
    >>> tbs1.block_containing(datetime.datetime(2010, 2, 1)) is None
    True
    >>> tbs1.block_containing(datetime.datetime(2010, 1, 31)) is None
    False
    >>> tbs1.block_containing(datetime.datetime(2009, 11, 30)) is None
    True

    To understand the tests below, note that the first ISO week of a
    year is the one in which the year's first Thursday falls.  Thus,
    for instance, December 31, 2008, a Wednesday, is in the first week
    of 2009.
    >>> tbs2 = TimeBlockSpec("week", 1, datetime.datetime(2008, 12, 31))
    >>> [str(block) for block in tbs2]
    ['week 52 of 2008', 'week 1 of 2009']
    >>> tbs3 = TimeBlockSpec("week", 1, datetime.datetime(2010, 1, 1))
    >>> [str(block) for block in tbs3]
    ['week 52 of 2009', 'week 53 of 2009']
"""
    class BadResolution(ValueError):
        def __init__(self, resolution):
            self.resolution = resolution
        def __str__(self):
            return "TimeBlockSpec resolution must be 'week' or 'month', not '%s'" % self.resolution

    class TimeBlock(object):
        """Nested class for the TimeBlock objects themselves.
        >>> tbs = TimeBlockSpec("week", 200, datetime.datetime(2010, 2, 1))
        >>> b1 = TimeBlockSpec.TimeBlock(tbs, 2008, 52)
        >>> b2 = TimeBlockSpec.TimeBlock(tbs, 2009, 1)
        >>> b1.successor() == b2
        True
        >>> b1 < b2
        True
        >>> b3 = TimeBlockSpec.TimeBlock(tbs, 2009, 52)
        >>> b4 = TimeBlockSpec.TimeBlock(tbs, 2009, 53)
        >>> b5 = TimeBlockSpec.TimeBlock(tbs, 2010, 1)
        >>> b2 < b3
        True
        >>> b2.successor() == b3
        False
        >>> b1 < b2 < b3 < b4 < b5
        True
        >>> b3.successor() == b4
        True
        >>> b4.successor() == b5
        True
        """
        def __init__(self, spec, year, unit):
            self.spec = spec
            self.year = year
            self.unit = unit
            ## TODO: check for bad unit values (month 13, etc.)

        def left_edge(self):
            """Return the datetime object representing the earliest
            time that may be contained in this block."""
            if self.spec.resolution == "month":
                return datetime.datetime(self.year, self.unit, 1)
            elif self.spec.resolution == "week":
                return datetime.datetime.strptime("%d-W%d-1" % (self.year, self.unit), "%Y-W%W-%w")

        def right_edge(self):
            """Return the datetime object representing the earliest
            time that is *later than* any time that may be contained
            in this block.  In other words, the left_edge and
            right_edge methods follow the mathematical convention that
            ranges be 'closed on the left and open on the right'."""
            return self.successor(check_boundaries=False).left_edge()

        def successor(self, check_boundaries=True):
            """If the TimeBlock that chronologically follows this one
            is within the boundaries of the spec, OR if
            check_boundaries is set, return it.  Otherwise, return
            None."""
            if self.spec.resolution == "month":
                if self.unit == 12:
                    next_year = self.year + 1
                    next_unit = 1
                else:
                    next_year = self.year
                    next_unit = self.unit + 1
            elif self.spec.resolution == "week":
                ## According to Wikipedia s.v. "ISO week date", a year has 53 ISO weeks
                ## iff January 1 and/or December 31 of that year is on Thursday.
                if datetime.datetime(self.year, 1, 1).isoweekday() == 4 or \
                        datetime.datetime(self.year, 12, 31).isoweekday() == 4:
                    max_week = 53
                else:
                    max_week = 52
                if self.unit == max_week:
                    next_year = self.year + 1
                    next_unit = 1
                else:
                    next_year = self.year
                    next_unit = self.unit + 1
            else:
                raise self.BadResolution(self.spec.resolution)
            if check_boundaries and ((next_year, next_unit) >
                                     (self.spec.latest_block.year, self.spec.latest_block.unit)):
                return None
            else:
                return type(self)(self.spec, next_year, next_unit)

        def __cmp__(self, other):
            if other.spec != self.spec:
                return NotImplemented
            return cmp((self.year, self.unit), (other.year, other.unit))

        def __hash__(self):
            return hash((hash(self.spec), self.year, self.unit))

        def __str__(self):
            return "%s %d of %d" % (self.spec.resolution, self.unit, self.year)

    def __init__(self, resolution, periods, latest_block_contains=datetime.datetime.now()):
        self.resolution = resolution
        self.periods = periods
        self.latest_block = self.block_containing(latest_block_contains, False)
        if resolution == "week":
            earliest_block_contains = latest_block_contains - datetime.timedelta(weeks=periods)
        elif resolution == "month":
            original_total_months = (latest_block_contains.year * 12) + (latest_block_contains.month - 1)
            new_total_months = original_total_months - periods
            (new_year, new_month_zero_based) = divmod(new_total_months, 12)
            earliest_block_contains = latest_block_contains.replace(year=new_year, month=new_month_zero_based + 1)
        else:
            raise self.BadResolution(resolution)
        self.earliest_block = self.block_containing(earliest_block_contains, False)

    def __iter__(self):
        state = self.earliest_block
        while state:
            yield state
            state = state.successor()
            ## When we fall off the boundary of the spec, state.successor() will return None,
            ## and the while loop will terminate.

    def __eq__(self, other):
        return (self.resolution, self.periods, self.latest_block.year, self.latest_block.unit) == \
            (other.resolution, other.periods, other.latest_block.year, self.latest_block.unit)
    def __ne__(self, other):
        return not (self == other)

    def __hash__(self):
        return hash((self.resolution, self.periods, self.latest_block.year, self.latest_block.unit))

    def block_containing(self, dt, check_boundaries=True):
        """If dt, which must be a datetime object, is within the
        proper range, then this method returns the TimeBlock
        appropriate to this TimeBlockSpec will be returned; otherwise,
        this method returns None.  If check_boundaries is set to
        False, then the bounds-checking is skipped and a TimeBlock
        will always be returned."""
        if self.resolution == "week":
            iso_year, iso_week, iso_weekday = dt.isocalendar()
            result = self.TimeBlock(self, iso_year, iso_week)
        elif self.resolution == "month":
            result = self.TimeBlock(self, dt.year, dt.month)
        if check_boundaries and (result < self.earliest_block or result > self.latest_block):
            return None
        else:
            return result

class TaskDataPoint(object):
    """Represents the time that a particular user spent
    working on a particular task, binned into a certain TaskBlock."""
    def __init__(self, uid, block, task_type, tag_or_merge, work_time):
        ## This constructor is called from the TimeChart constructor below,
        ## and in that code, the user is represented by a UID rather than a
        ## User object (because, for the sake of efficiency, we are using a
        ## ValuesQuerySet to look up response/result information).  Instead
        ## of instantiating a User object here, we are just saving the UID.
        self.uid = uid
        self.block = block
        self.task_type = task_type
        self.tag_or_merge = tag_or_merge
        self.work_time = work_time

class TaskDataSet(object):
    """Aggregates information from a set of TaskDataPoint objects to
    get the average and median times spent tagging and merging."""
    def __init__(self, points, task_type):
        """The 'points' argument must be a non-empty iterable containing TaskDataPoint objects,
        and the 'task_type' argument must be either 'tagging' or 'merging'."""
        self.task_type = task_type
        def median(xs):
            ordered = sorted(list(xs))
            magnitude = len(xs)
            if magnitude % 2:
                ## odd number of points
                return ordered[magnitude / 2]
            else:
                return (ordered[magnitude / 2 - 1] + ordered[magnitude / 2]) / 2.0
        tag_point_time = [p.work_time for p in points if p.tag_or_merge == "tagging"]
        merge_point_time = [p.work_time for p in points if p.tag_or_merge == "merging"]
        self.work_time = sum(tag_point_time) + sum(merge_point_time)
        if tag_point_time:
            self.tagging_time_average = sum(tag_point_time) / len(tag_point_time)
            self.tagging_time_median = median(tag_point_time)
        else:
            self.tagging_time_average = None
            self.tagging_time_median = None
        if merge_point_time:
            self.merging_time_average = sum(merge_point_time) / len(merge_point_time)
            self.merging_time_median = median(merge_point_time)
        else:
            self.merging_time_average = None
            self.merging_time_median = None

    def as_dict(self):
        result = {"work_time": self.work_time, "task_type": self.task_type}
        if self.tagging_time_average:
            result["tagging_time_average"] = self.tagging_time_average
            result["tagging_time_median"] = self.tagging_time_median
        if self.merging_time_average:
            result["merging_time_average"] = self.merging_time_average
            result["merging_time_median"] = self.merging_time_median
        return result

class TaskBin(object):
    """Aggregates information about all the tasks, of various types,
    that one user does within one time block."""
    def __init__(self, user, block, points):
        self.user = user
        self.block = block
        points_by_type = {}
        for point in points:
            tt = point.task_type
            if tt in points_by_type:
                points_by_type[tt].add(point)
            else:
                points_by_type[tt] = set([point])
        self.data_sets = [TaskDataSet(points_by_type[tt], tt)
                          for tt in sorted(points_by_type.keys())]
        self.work_time = sum([tds.work_time for tds in self.data_sets])

    def as_dict(self):
        return {"work_time": self.work_time,
                "data_sets": [ds.as_dict() for ds in self.data_sets]}

class TimeChart(object):
    """Generates a report on clickwork usage based on the given spec.
    Among all the classes related to timesheet generation, this is the
    only one that actually touches the database.  The object's
    'report' attribute is a two-level dict, where
    tc.report[uid][block] is a TaskBin of information regarding what
    the given user did during the given time block."""
    def __init__(self, spec, users):
        def value_to_point(value, tag_or_merge):
            """Translates a value-dict generated from the queries
            below into a TaskDataPoint object."""
            block = spec.block_containing(value["end_time"])
            if block:
                return TaskDataPoint(value["user"], block, value["project_type"],
                                     tag_or_merge, value["seconds"])
            else:
                ## The end_time must be outside the boundaries of the spec.
                return None
        def generate_points():
            ## For date-mangling we need to use PostgreSQL-specific functions.
            ## SQLite WILL BREAK on these.
            def query_from(klass):
                """Generate a QuerySet object from the given model class, which may be 
                either Response or Result."""
                if spec.resolution == "week":
                    y = "isoyear"
                else:
                    y = "year"
                select_arg = {"seconds": "extract(epoch from end_time - start_time)",
                              "project_type": "main_project.type"}
                qs = klass.objects.extra(select=select_arg, tables=["main_task", "main_project"],
                                         where=["task_id = main_task.id", "main_task.project_id = main_project.id"]
                                         ).filter(end_time__gte=spec.earliest_block.left_edge(),
                                                  end_time__lt=spec.latest_block.right_edge(),
                                                  user__in=users).values("user",
                                                                         "project_type",
                                                                         "seconds",
                                                                         "end_time")
                return qs
            for value in query_from(Response):
                point = value_to_point(value, "tagging")
                if point:
                    yield point
            for value in query_from(Result):
                point = value_to_point(value, "merging")
                if point:
                    yield point
        points_by_uid_and_block = {}
        for point in generate_points():
            uid = point.uid
            if uid in points_by_uid_and_block:
                points_by_block = points_by_uid_and_block[uid]
                if point.block in points_by_block:
                    points_by_block[point.block].append(point)
                else:
                    points_by_block[point.block] = [point]
            else:
                points_by_uid_and_block[uid] = {point.block: [point]}
        bins_by_uid_and_block = {}
        for (uid, points_by_block) in points_by_uid_and_block.iteritems():
            bins_by_block = {}
            for (block, points) in points_by_block.iteritems():
                bins_by_block[block] = TaskBin(User.objects.get(pk=uid), block, points)
            bins_by_uid_and_block[uid] = bins_by_block
        self.report = bins_by_uid_and_block

class TimesheetForm(forms.Form):
    users = forms.ModelMultipleChoiceField(queryset=User.objects.filter(is_active=True).order_by("username"),
                                           required=False,
                                           widget=forms.SelectMultiple(attrs={"size": 7}))
    groups = forms.ModelMultipleChoiceField(queryset=Group.objects.all().order_by("name"),
                                            required=False,
                                            widget=forms.SelectMultiple(attrs={"size": 7}))
    periods = forms.IntegerField(max_value=12,
                                 initial="3",
                                 # try to make this an HTML5 number form field
                                 widget=forms.TextInput(attrs={"type": "number",
                                                               "min": "1",
                                                               "max": "12",
                                                               "step": "1"}))
    resolution = forms.ChoiceField(choices=(("week", "weeks"),
                                            ("month", "months")),
                                   initial="week")
    ending_date = forms.DateField(initial=datetime.date.today())

    def clean(self):
        if not (self.cleaned_data["users"] or self.cleaned_data["groups"]):
            raise forms.ValidationError("You must select at least one user or group.")
        return self.cleaned_data

@login_required
@get
def timesheet(guts):
    """Generate a TimeChart object from the given spec parameters and
    then translate it into a viewable format."""
    if guts.user.is_staff:
        template = get_template("timesheet.html")
        if all([p in guts.parameters for p in ("resolution", "periods", "ending_date")]):
            form = TimesheetForm(guts.parameters)
        else:
            form = TimesheetForm()
        if form.is_bound and form.is_valid():
            resolution = form.cleaned_data["resolution"]
            periods = form.cleaned_data["periods"]
            spec = TimeBlockSpec(resolution, periods,
                                 form.cleaned_data["ending_date"])
            users = set(form.cleaned_data["users"])
            for group in form.cleaned_data["groups"]:
                for user in group.user_set.all():
                    users.add(user)
            chart = TimeChart(spec, users)
            rows = []
            for (uid, bins_by_block) in chart.report.iteritems():
                user = User.objects.get(pk=uid)
                cells = []
                for block in spec:
                    if block in bins_by_block:
                        cells.append(bins_by_block[block].as_dict())
                    else:
                        cells.append({"data_sets": [], "work_time": 0})
                rows.append({"user": user.username, "cells": cells})
            headers = [str(block) for block in spec]
            return TemplateResponse(template, {"form": form, "headers": headers,
                                               "rows": sorted(rows,
                                                              key=lambda r: r["user"]),
                                               "resolution": resolution,
                                               "periods": periods})
        else:
            return TemplateResponse(template, {"form": form})
    else:
        return ForbiddenResponse("The timesheet pages are only accessible to staff.")
