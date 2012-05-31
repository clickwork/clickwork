#!/usr/bin/python

import sys
import os

sys.stdout = sys.stderr
path = os.path.dirname(os.path.abspath(__file__))
#ugly hack until packaging is more sane (v2.0)
sys.path.insert(0, '/usr/local/lib/python2.6/dist-packages')
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(path, ".."))
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'

import django.core.handlers.wsgi

application = django.core.handlers.wsgi.WSGIHandler()

if __name__ == '__main__':
    from wsgiref.simple_server import make_server
    httpd = make_server('0.0.0.0', 9000, application)
    print "Listening on port 9000...."
    httpd.serve_forever()
