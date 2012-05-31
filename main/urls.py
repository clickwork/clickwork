from django.conf import settings
from django.conf.urls.defaults import *
from django.contrib.auth import views

urlpatterns = patterns('main.views',
    # Example:
    (r'^project/(?P<project_id>\d+)/api/(?P<url>.*)$', 'project.project_api'),
    (r'^task/(?P<task_id>\d+)/$', 'task.task_view'),
    (r'^review/(?P<review_id>\d+)/$', 'task.task_review'),
    (r'^review/$', 'task.task_adhoc_review'),
    (r'^review/next/$', 'task.next_review'),
    (r'^next_task/', 'base.next_task'),
    (r'^abandon/', 'base.abandon_wip'),
    (r'^$', 'base.home'),
    (r'^about/$', 'base.about'),
    (r'^timesheet/', 'timesheets.timesheet'),
    (r'^projects/', 'overview.all_projects_brief'),
    (r'^projects-long/', 'overview.all_projects'),
    (r'^project/(\d+)/$', 'overview.one_project'),
    (r'^project/(\d+)/stats/$', 'project.project_stats'),
    (r'^project/(\d+)/agreement/$', 'project.project_agreement'),
    (r'^project/(\d+)/export/$', 'project.project_export'),
    (r'^project/(\d+)/upload/', 'project.project_upload'),
    (r'^groups/', 'overview.all_groups'),
    (r'^group/(\d+)/$', 'overview.one_group'),
    (r'^users/', 'overview.all_users'),
    (r'^user/([A-Za-z0-9@+._-]+)/$', 'overview.one_user'),
    (r'^user/([A-Za-z0-9@+._-]+)/responses/$', 'user.recent_responses'),
    (r'^user/([A-Za-z0-9@+._-]+)/results/$', 'user.recent_results'),
    (r'^remerge/(\d+)/$', 'task.unmerge'),
    (r'^wips/$', 'task.wip_review'),
    (r'^track/$', 'base.track_page_visit')
)

## If the "main.types.bar_baz module" has a urlpatterns variable
## defining a "foo" URL pattern, this will be translated into
## "/project-type/bar-baz/foo".
for task_type in settings.TASK_TYPES:
    mod = __import__("main.types.%s" % task_type, None, None, ["urlpatterns"])
    if hasattr(mod, "urlpatterns"):
        urlpatterns += patterns("main.types",
                                ("^project-type/%s/" % task_type.replace("_", "-"),
                                 include("main.types." + task_type)))

urlpatterns += patterns("main.wrapper",
                        (r"^wrap1/$", "smoke_test_1"),
                        (r"^wrap2/$", "smoke_test_2")
                        )

urlpatterns += patterns('django.contrib.auth.views',
                        (r'^accounts/logout/$', 'logout', {'template_name': 'logout.html'}),
                        (r'^accounts/login/$', 'login', {'template_name': 'login.html'}))

