"""
>>> u = User.objects.create_user("maxwell_smart", "smart@example.com", "abc")
>>> u.full_clean()
>>> u.save()
>>> u.username
'maxwell_smart'

>>> from main.models import Project
>>> p = Project(admin=u, title="Test Project", description="Testing project.", type="simple", annotator_count=1, priority=3)
>>> p.full_clean()
>>> p.save()

>>> from main.wrapper import RequestGuts
>>> rg = RequestGuts()
>>> rg.user = u
>>> from main.views.overview import one_project
>>> tr = one_project.dispatcher['GET'](rg, p.id)
>>> tr.data['project']['title']
u'Test Project'
>>> tr.data['assignments']
[]
>>> p.delete()
"""
from django.test.client import Client
from django.test import TestCase
from django.contrib.auth.models import User, Group
from django.conf import settings
from main.models import Project, Review, Response

from main.wrapper import RequestGuts, ForbiddenResponse
from main.helpers import *
import main.views.base
import main.types
from main.types.simple import SimpleProject, SimpleTask, SimpleResponse

from main.moretests.expectation import Conditions, WebTarget, ViewExpectation

from main.templatetags import url

import datetime
import doctest
import sys
import unittest

from cStringIO import StringIO
from base64 import b64decode
from zipfile import ZipFile, ZIP_DEFLATED

class WrapperTests(TestCase):
    def setUp(self):
        u = User.objects.create_user("testuser", "foo@example.com", "abc")
        u.full_clean()
        u.save()

    def test_login(self):
        self.failUnless(self.client.login(username='testuser', password='abc'))
        
    def test_home_post(self):
        """
        You can't post to /; it's @get only.
        """
        self.test_login()
        target = WebTarget("POST", main.views.base.home, statuses=(405,))
        expectation = ViewExpectation(Conditions.null(), target)
        expectation.check(self)

class BaseViews(TestCase):

    def setUp(self):
        u = User.objects.create_user("testuser_base", "foo@example.com", "abc")
        u.full_clean()
        u.save()
        self.rg = RequestGuts()
        self.rg.user = u 
    
    def test_home(self):
        self.client.login(username="testuser_base", password="abc")
        target = WebTarget("GET", main.views.base.home)
        def honey_i_am_home(input_context, output_context):
            """Check for JSON output that could only have come from the home page."""
            return all(["respondable_tasks" in output_context,
                        "respondable_task_count" in output_context,
                        "resolvable_tasks" in output_context,
                        "resolvable_task_count" in output_context,
                        "recent_responses" in output_context,
                        "reviews" in output_context])
        def home_empty_counts(input_context, output_context):
            return output_context["respondable_task_count"] == 0 and \
                output_context["resolvable_task_count"] == 0
        expectation = ViewExpectation(Conditions((), (honey_i_am_home, home_empty_counts),()),
                                      target)
        expectation.check(self)

class UrlFilter(TestCase):
    def runTest(self):
        for test_case in url.test_cases:
            self.assertEqual(test_case[1], url.urlfilter(test_case[0]), "Failed on urlifying %s" % test_case[0]) 

class ProjectViews(TestCase):
    def setUp(self):
        u = User.objects.create_user("testuser_getnexttask", "foo@example.com", "abc")
        u.full_clean()
        u.save()
        g = Group(name="test group")
        g.full_clean()
        g.save()
        u.groups.add(g)
        u.full_clean()
        u.save()
        
        p = SimpleProject(admin=u, title="Test Project", description="Testing project.", type="simple", annotator_count=1, priority=3)
        p.full_clean()
        p.save()
        p.annotators.add(g)
        p.full_clean()
        p.save()
        t = SimpleTask(question="test question", project=p)
        t.full_clean()
        t.save()
        r = SimpleResponse(task=t, answer="test answer", comment="test comment",
                           start_time=datetime.datetime(2000, 1, 1), user=u)
        r.full_clean()
        r.save()
        t.completed_assignments=1
        t.completed=True
        t.full_clean()
        t.save()
        self.t = t
        self.user = u
        self.p = p

    def export_project_simple(self):
        def export_attrs(input_context, output_context):
            zipped_64 = output_context["contents_in_base64"]
            zipped = ZipFile(StringIO(b64decode(zipped_64)), "r", ZIP_DEFLATED)
            permissions_are_right = [zi.external_attr == \
                                         settings.CLICKWORK_EXPORT_FILE_PERMISSIONS << 16L
                                     for zi in zipped.infolist()]
            return all(permissions_are_right)
        self.client.login(username="testuser_getnexttask", password="abc")
        target = WebTarget("GET", main.views.project.project_export, args=(self.p.id,))
        expectation = ViewExpectation(Conditions.post(export_attrs), target)
        output_context = expectation.check(self)
    
    def export_project_dict(self):
        self.client.login(username="testuser_getnexttask", password="abc")
        target = WebTarget("GET", main.views.project.project_export, args=(self.p.id,))
        expectation = ViewExpectation(Conditions.null(), target)
        expectation.check(self)

class GetNextTask(TestCase):
    def setUp(self):
        u = User.objects.create_user("testuser_getnexttask", "foo@example.com", "abc")
        u.full_clean()
        u.save()
        g = Group(name="test group")
        g.full_clean()
        g.save()
        u.groups.add(g)
        u.full_clean()
        u.save()

        p = Project(admin=u, title="Test Project", description="Testing project.", type="simple", annotator_count=1, priority=3)
        p.full_clean()
        p.save()
        p.annotators.add(g)
        p.full_clean()
        p.save()
        t = SimpleTask(question="test question", project=p)
        t.full_clean()
        t.save()
        self.t = t
        self.user = u

    def get_user_task(self):
        task = Task.objects.next_for(self.user)
        wip = WorkInProgress(user=self.user, task=task)
        wip.full_clean()
        wip.save()
        task = Task.objects.next_for(self.user)
        self.failUnlessEqual(task, None)

    @property
    def task_expectation(self):
        next_task_target = WebTarget("GET", main.views.base.next_task,
                           final_views=(main.views.task.task_view,))
        def task_id_expected(input_context, output_context):
            return output_context["task"]["id"] == self.t.id
        return ViewExpectation(Conditions.post(task_id_expected), next_task_target)

    def get_next_task_view(self):
        self.client.login(username="testuser_getnexttask", password="abc")
        ## get the next task
        self.task_expectation.check(self)
        ## tweak the database to put a response and a review in
        response = Response(task=self.t, user=self.user, start_time=datetime.datetime.now())
        response.full_clean()
        response.save()
        review = Review(response=response, comment="I have reviewed this task.")
        review.full_clean()
        review.save()
        ## check to see if next_task now redirects to review
        ## if we actually execute the view code, we will get an error,
        ## because the task associated with the review has no result;
        ## therefore the code below is a bit hackish
        review_target = WebTarget("GET", main.views.base.next_task, statuses=(301, 302))
        def redirects_to_review(input_context, output_context):
            return "/review/next/" in output_context["__redirected_to__"]
        review_expectation = ViewExpectation(Conditions.post(redirects_to_review), review_target)
        review_expectation.check(self)
        ## tweak the database to complete the review
        review.complete = True
        review.full_clean()
        review.save()
        ## try getting the next task again
        self.task_expectation.check(self)

    def get_next_task_should_fail(self):
        """Try to get a task with the wrong user's authentication."""
        other_user = User.objects.create_user("nobody_special", "foo@example.com", "abc")
        ## this should work...
        self.client.login(username="testuser_getnexttask", password="abc")
        self.task_expectation.check(self)
        ## ...and this shouldn't
        self.client.login(username="nobody_special", password="abc")
        forbidden_task_target = WebTarget("GET", main.views.task.task_view,
                                          args=(self.t.id,), statuses=(403,))
        forbidden_expectation = ViewExpectation(Conditions.null(), forbidden_task_target)
        forbidden_expectation.check(self)

def suite():
    from main.moretests.fresh_eyes_test import FreshEyes
    from main.moretests.tagmerge import SimpleTagMerge, KeepApart, UserCreationRestriction, WipRevocation
    from main.moretests.twostage import TwoStageTestCase, MultilingoTestCase, NeedingCorrection, AutoReview
    from main.moretests.expectation import ExpectationSmokeTest
    import main.views.timesheets
    suite = unittest.TestSuite()
    suite.addTest(FreshEyes())
    suite.addTest(doctest.DocTestSuite())
    suite.addTest(doctest.DocTestSuite(main.views.timesheets))
    suite.addTests((WrapperTests("test_home_post"),
                    BaseViews("test_home"),
                    ProjectViews("export_project_simple"),
                    ProjectViews("export_project_dict"),
                    GetNextTask("get_user_task"),
                    GetNextTask("get_next_task_view"),
                    GetNextTask("get_next_task_should_fail"),
                    SimpleTagMerge(),
                    KeepApart(),
                    UserCreationRestriction(),
                    TwoStageTestCase(),
                    ExpectationSmokeTest(),
                    WipRevocation(),
                    UrlFilter(),
                    NeedingCorrection(),
                    AutoReview(),
                    ))
    return suite
