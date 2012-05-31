#!/usr/bin/python
"""Set up the fixture that will be used for the needs_fresh_eyes test (CW-33).
For the sake of using the test client and the expectations code that depends on it,
this is structured as a subclass of TestCase, but it's really not supposed to run
in the regular series of unit tests."""
from django.conf import settings
from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase
from main.moretests.expectation import Conditions, WebTarget, ViewExpectation
from main.types import type_list
import main.views.base
import main.views.project
import os
import sys
import user_management.views

class NeedsFreshEyesSetup(TestCase):
    def login_as(self, username):
        """Have the Web client log in with the given username,
        assuming that the password is the same as the username, and
        signal a test failure if the login is unsuccessful."""
        self.assert_(self.client.login(username=username, password=username),
                     "Login as " + username + " failed")

    def set_up_users(self):
        superuser = User.objects.create_user("superuser",
                                             "super@example.com",
                                             "superuser")
        superuser.is_superuser = True
        superuser.is_staff = True
        superuser.save()
        self.login_as("superuser")
        new_user_target = WebTarget("POST", user_management.views.new_user)
        expectation = ViewExpectation(Conditions.null(), new_user_target)
        for name in ("alice", "bob", "carol", "dave"):
            ## Test creation of the account.
            input_context = {"username": name,
                             "first_name": name.capitalize(),
                             "last_name": "Example",
                             "email": "%s@example.com" % name}
            expectation.check(self, input_context)
            ## Park the corresponding User object as an attribute, and
            ## reset its (randomly-generated) password,
            ## so that other test code can simulate logins over the client.
            u = User.objects.get(username=name)
            self.__dict__[name] = u
            u.set_password(name)
            u.save()
        g = Group.objects.create(name="taggers_and_mergers")
        for member in (self.bob, self.carol, self.dave):
            g.user_set.add(member)
        g.save()
        self.taggers_and_mergers = g

    @property
    def project_type(self):
        return "simple"

    @property
    def project_title(self):
        return "needs_fresh_eyes test"

    @property
    def quiz(self):
        return {"What is your name?":
                    {self.bob:   "Sir Launcelot of Camelot",
                     self.carol: "Sir Galahad of Camelot",
                     self.dave:  "Arthur, King of the Britons"},
                "What is your quest?":
                    {self.bob:   "To seek the Holy Grail",
                     self.carol: "To seek the Holy Grail",
                     self.dave:  "To seek the Holy Grail"},
                "What is your favorite colour?":
                    {self.bob:   "Blue",
                     self.carol: "Yellow",
                     self.dave:  "An African or a European colour?"}}

    def initialize_project(self):
        t = type_list[self.project_type].project
        self.project = t.objects.create(title=self.project_title,
                                        type=self.project_type,
                                        admin=self.alice,
                                        annotator_count=2,
                                        needs_fresh_eyes=True,
                                        priority=1,
                                        description="A test project")
        self.project.annotators.add(self.taggers_and_mergers)
        self.project.save()

    def populate_project(self):
        f = SimpleUploadedFile("questions", "\n".join(self.quiz.keys()))
        f.open("rb")
        context = {"action": "Upload", "upload": f}
        target = WebTarget("POST", main.views.project.project_upload,
                           args=(self.project.id,))
        expectation = ViewExpectation(Conditions.null(), target)
        expectation.check(self, context)

    def tag_project(self):
        ## Each user should tag two tasks.
        for i in range(2):
            for user in (self.bob, self.carol, self.dave):
                self.login_as(user.username)
                next_task_target = WebTarget("GET", main.views.base.next_task,
                                             final_views=(main.views.task.task_view,))
                next_task_expectation = ViewExpectation(Conditions.null(),
                                                        next_task_target)
                output_context = next_task_expectation.check(self)
                question = output_context["question"]
                answer_input_context = {"answer": self.quiz[question][user],
                                        "comment": "generated in testing"}
                answer_target = WebTarget("POST", main.views.task.task_view,
                                          (output_context["task"]["id"],),
                                          final_views=(main.views.task.task_view,
                                                       main.views.base.home))
                answer_expectation = ViewExpectation(Conditions.null(), answer_target)
                answer_expectation.check(self, answer_input_context)
                print >>sys.stderr, "User", user.username, "answered", question
                ## At this point the user is holding a WIP for the third task,
                ## but we want that WIP to be released.
                abandon_target = WebTarget("POST", main.views.base.abandon_wip,
                                           statuses=(302, 200))
                abandon_expectation = ViewExpectation(Conditions.null(), abandon_target)
                abandon_expectation.check(self)

    def runTest(self, result=None):
        self.set_up_users()
        self.initialize_project()
        self.populate_project()
        self.tag_project()
        self.project.mergers.add(self.taggers_and_mergers)
        old_stdout = sys.stdout
        fixture_file = os.path.join(settings.BASE_PATH, "main", "fixtures", "fresh_eyes.json")
        sys.stdout = open(fixture_file, "wb")
        call_command("dumpdata", indent=2, natural=True, exclude=["contenttypes.contenttype",
                                                                  "auth.permission"])
        sys.stdout = old_stdout
