from django.conf.urls.defaults import *

urlpatterns = patterns('user_management.views',
  (r'^$', 'change_password'),
  (r'^new/$', 'new_user'),
)
