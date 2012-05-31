from django import forms
from django.contrib.auth.models import User, AnonymousUser
from django.contrib.sessions.backends.db import SessionStore
from django.core.context_processors import csrf
from django.core.urlresolvers import reverse
import django.db.models
from django.db.models.query import QuerySet
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect, HttpResponseServerError, HttpResponseNotFound, HttpResponseForbidden, HttpResponseNotAllowed, QueryDict, MultiValueDict, Http404
from django.template import RequestContext
from django.template.loader import get_template

from base64 import b64encode
from functools import wraps
from urlparse import urlsplit, urlunsplit
from datetime import datetime, date
import simplejson as json

import sys

import logging
logger = logging.getLogger(__name__)

"""Classes to mediate between the business logic in the views and the
HTTP-specific classes in Django."""

HTML = "text/html"
JSON = "text/plain" # "application/json"?

class WrapperException(Exception):
    pass

###
### RequestGuts
###

class RequestGuts(object):
    r"""The parts of an HttpRequest that we actually want the views to see.

    >>> rg = RequestGuts()
    >>> rg.parameters = QueryDict("dish=spinach&dish=souffl%c3%a9", encoding="utf-8")
    >>> rg.parameters["dish"]
    u'souffl\xe9'
    >>> rg.parameters.getlist("dish")
    [u'spinach', u'souffl\xe9']
    >>> isinstance(rg.user, AnonymousUser)
    True
    """
    def __init__(self, request=None, user=None, session=None):
        assert not (bool(request) and bool(user)), \
            "The RequestGuts constructor may take a request or a user argument, but not both"
        assert not (bool(request) and bool(session)), \
            "The RequestGuts constructor may take a request or a session, but not both"
        if request:
            if request.method == "GET":
                self.parameters = request.GET
            elif request.method == "POST":
                self.parameters = request.POST
            else:
                raise self.MethodNotSupported(http.method)
            self.files = request.FILES
            self.user = request.user
            self.session = request.session
            self.client_ip = request.META.get('HTTP_X_FORWARDED_FOR', None) or request.META.get("REMOTE_ADDR", None) or "unknown ip"
        else:
            self.parameters = QueryDict("")
            self.files = MultiValueDict({})
            if user:
                self.user = user
            else:
                self.user = AnonymousUser()
            if session:
                self.session = session
            else:
                self.session = SessionStore()
            self.client_ip = "[NOT_HTTP]"

    def _log(self, level, message):
        logger.log(level, message, extra={"user": self.user.username,
                                          "client_ip": self.client_ip})

    def log_debug(self, message):
        self._log(10, message)

    def log_info(self, message):
        self._log(20, message)

    def log_warning(self, message):
        self._log(30, message)

    def log_error(self, message):
        self._log(40, message)

    def log_critical(self, message):
        self._log(50, message)

    class MethodNotSupported(WrapperException):
        def __init__(self, method):
            self.method = method
            self.message = "Unhandled HTTP exception %s" % self.method

###
### ResponseSeed, its subclasses, and its collaborators
###

class Encoder(json.JSONEncoder):
    """Custom class for encoding our objects to JSON.  By default any
    model will be represented as a dict containing its class name and
    primary-key value.  If you want something more sophisticated, give
    the class a to_json property (NOT a method) that returns a
    JSON-serializable object, or an as_dict method that returns a
    JSON-serializable dict.  Note that right now there is no
    corresponding custom decoder."""
    def default(self, obj):
        if hasattr(obj, "to_json"):
            return obj.to_json
        elif hasattr(obj, "as_dict"):
            return obj.as_dict()
        elif isinstance(obj, User):
            return {"username": obj.username, "pk": obj.pk}
        elif isinstance(obj, django.db.models.Model):
            return {"__model__": str(type(obj)), "pk": obj.pk}
        elif isinstance(obj, forms.Form):
            result = {"valid": obj.is_valid(),
                      "errors": obj.errors,
                      "bound": obj.is_bound}
            if obj.is_valid():
                result["data"] = obj.cleaned_data
            return result
        elif isinstance(obj, QuerySet):
            return list(obj)
        elif isinstance(obj, datetime) or isinstance(obj, date):
            return obj.isoformat()
        print >>sys.stderr, "*** Trouble encoding an object of type %r" % type(obj)
        return json.JSONEncoder.default(self, obj)

class ResponseSeed(object):
    """The parts of an HttpResponse that we trust views to create."""
    def sprout(self, context, format):
        if format == "html":
            return self.sprout_html(context)
        elif format == "json":
            return self.sprout_json(context)
        else:
            raise self.FormatNotSupported(format)

    def sprout_html(self, context):
        raise NotImplementedError, "ResponseSeed is an abstract class"

    def sprout_json(self, context):
        raise NotImplementedError, "ResponseSeed is an abstract class"

    class FormatNotSupported(WrapperException):
        def __init__(self, format):
            self.format = format
            self.message = "Cannot handle output format %s" % self.format

class ErrorResponse(ResponseSeed):
    """Use for server errors."""
    def __init__(self, heading, message):
        """The heading and message may contain markup."""
        self.heading = heading
        self.message = message

    def sprout_html(self, context):
        error_template = get_template("error.html")
        context.update({"error_heading": self.heading, "error_message": self.message})
        body = error_template.render(context)
        return HttpResponseServerError(body, content_type=HTML)

    def sprout_json(self, context):
        body = json.dumps({"error_heading": self.heading, "error_message": self.message},
                          indent=2)
        return HttpResponseServerError(body, content_type=JSON)

class NotFoundResponse(ResponseSeed):
    """Use for objects not found."""
    def __init__(self, message):
        """The message may contain markup."""
        self.message = message

    def sprout_html(self, context):
        not_found_template = get_template("not-found.html")
        context.update({"not_found_message": self.message})
        body = not_found_template.render(context)
        return HttpResponseNotFound(body, content_type=HTML)

    def sprout_json(self, context):
        body = json.dumps({"not_found_message": self.message})
        return HttpResponseNotFound(body, content_type=JSON)

class ForbiddenResponse(ResponseSeed):
    """Use when a page or activity is forbidden, and when other layers,
    like the @login_required decorator, haven't caught the problem."""
    def __init__(self, message):
        """The message may contain markup."""
        self.message = message

    def sprout_html(self, context):
        forbidden_template = get_template("forbidden.html")
        context.update({"forbidden_message": self.message})
        body = forbidden_template.render(context)
        return HttpResponseForbidden(body, content_type=HTML)

    def sprout_json(self, context):
        body = json.dumps({"forbidden_message": self.message})
        return HttpResponseForbidden(body, content_type=JSON)

class DefaultResponse(ResponseSeed):
    """A response for representing JSON-serializable data where no
    template is available."""
    def __init__(self, data, status=200):
        self.data = data
        self.status = status

    def sprout_html(self, context):
        default_template = get_template("json.html")
        dump = json.dumps(self.data, cls=Encoder, indent=2)
        context.update({"json": dump})
        body = default_template.render(context)
        return HttpResponse(body, content_type=HTML)

    def sprout_json(self, context):
        body = json.dumps(self.data, cls=Encoder, indent=2)
        return HttpResponse(body, status=self.status, content_type=JSON)

class AttachmentResponse(DefaultResponse):
    """A response for returning an attached file."""
    def __init__(self, name, content_type, contents):
        self.name = name
        self.content_type = content_type
        self.contents = contents

    def sprout_html(self, context):
        response = HttpResponse(self.contents, content_type=self.content_type)
        response["Content-Disposition"] = "attachment; filename=%s" % self.name
        return response

    def sprout_json(self, context):
        body = json.dumps({"name": self.name,
                           "content_type": self.content_type,
                           "contents_in_base64": b64encode(self.contents)},
                          indent=2)
        return HttpResponse(body, content_type=JSON)

class TemplateResponse(DefaultResponse):
    """A normal response involving data that can be sent to fill in a
    template.  Since the template is specific to HTML responses, when
    a JSON response is desired, this class is indistinguishable
    from DefaultResponse."""
    def __init__(self, template, data, status=200):
        self.data = data
        self.template = template
        self.status = status

    def sprout_html(self, context):
        context.update(self.data)
        body = self.template.render(context)
        return HttpResponse(body, status=self.status, content_type=HTML)

class ModelResponse(DefaultResponse):
    """Returns a page representing a given Model object.  In HTML, if
    get_absolute_url is defined for that object, the user will be
    redirected there."""
    def __init__(self, model):
        self.model = model

    def sprout_html(self, context):
        if hasattr(self.model, "get_absolute_url"):
            return HttpResponseRedirect(self.model.get_absolute_url())
        else:
            other_seed = DefaultResponse(self.model)
            return other_seed.sprout(context, "html")

class ViewResponse(ResponseSeed):
    """Returns the page associated with a given view;
    see the documentation for django.core.urlresolvers.reverse."""
    def __init__(self, view, *args, **kwargs):
        self.view = view
        self.args = args
        self.kwargs = kwargs
        self.url = reverse(view, args=args, kwargs=kwargs)

    def sprout(self, context, format):
        return HttpResponseRedirect(append_format(self.url, format))

class RefererResponse(ResponseSeed):
    """Use this for cases where a page redirects to its referer.
    This is a common idiom when executing a POST, for example."""
    def sprout(self, context, format):
        if "referer" not in context:
            message = "This page should redirect back to its referring page, but the HTTP_REFERER metadata cannot be found."
            other_seed = ErrorResponse("No referer", message)
            other_seed.sprout(context, format)
        else:
            return HttpResponseRedirect(append_format(context["referer"], format))

###
### Wrapper
###
def append_format(url, format):
    """This method adds the given response format parameter to the
    given URL.

    Note that if the given URL already has a response format
    parameter, this method will just add another one.  That is OK,
    because (a) the QueryDict.get method will pull out the most
    recently added value of the parameter, and (b) if we start
    worrying about trying to detect the \"response_format\" in the
    query string, we also have to worry about various ways that
    \"response_format\" could be escaped."""
    (scheme, netloc, path, query, fragment) = urlsplit(url)
    new_parameter = "response_format=" + format
    if query == "":
        new_query = new_parameter
    else:
        new_query = query + "&" + new_parameter
    return urlunsplit((scheme, netloc, path, new_query, fragment))

def dispatch_on_method(f, d):
    """Decorator that takes a function f, whose metadata will be
    passed through to the decorated function, and a dict mapping HTTP
    methods onto closures that take (guts, *args, **kwargs) and return
    ResponseSeed objects.  Returns a function g that will take an HTTP
    request, and if the request method is supported, the appropriate
    closure will be invoked.

    Given that decorated function g, g.dispatcher is the dict that was
    passed in as the second argument to dispatch_on_method.  Thus, to
    test a wrapped function's functionality without an HTTP client,
    g.dispatcher["GET"](guts, ...) will return a ResponseSeed that the
    test code may inspect.

    I do not know what will happen if the values of d never invoke
    f."""
    @wraps(f)
    def g(request, *args, **kwargs):
        if request.method in d:
            guts = RequestGuts(request)
            try:
                seed = d[request.method](guts, *args, **kwargs)
            except Http404, e:
                seed = NotFoundResponse(e.message)
            except Exception, e:
                log_message = "%s to %s raised %s: %s" % (request.method,
                                                          request.path,
                                                          type(e).__name__,
                                                          str(e))
                guts.log_error(log_message)
                raise
            format = guts.parameters.get("response_format", "html")
            context = RequestContext(request, {"referer": request.META.get("HTTP_REFERER", None)})
            response = seed.sprout(context, format)
            if response.status_code >= 400:
                log_message = "%s to %s yields code %d" % (request.method, request.path, response.status_code)
                if hasattr(seed, "message"):
                    log_message += ": " + seed.message
                if 400 <= response.status_code < 500:
                    guts.log_warning(log_message)
                else:
                    guts.log_error(log_message)
        else:
            response = HttpResponseNotAllowed(d.keys())
        return response
    g.dispatcher = d
    return g

def get(f):
    return dispatch_on_method(f, {"GET": lambda guts, *args, **kwargs: f(guts, *args, **kwargs)})

def get_or_post(f):
    return dispatch_on_method(f, {"GET": lambda guts, *args, **kwargs: f(True, guts, *args, **kwargs),
                                  "POST": lambda guts, *args, **kwargs: f(False, guts, *args, **kwargs)})
###
### Convenience functions to use within tests.
###
def fake_get(view, *args, **kwargs):
    return view.dispatcher["GET"](*args, **kwargs)

def fake_post(view, *args, **kwargs):
    return view.dispatcher["POST"](*args, **kwargs)

###
### Smoke tests
###

@get
def smoke_test_1(guts):
    return DefaultResponse({"foo": ["bar", "baz"]})

from django.template import Template
from django.contrib.auth.decorators import login_required

class WrapperSmokeTestForm(forms.Form):
    quux = forms.CharField(max_length=100)

template = Template("""{% extends "base.html" %}
{% block title %}Wrapper Smoke Test{% endblock %}
{% block heading %}The Studly Quux says {{ quux|default:"nothing" }} to {{ user }}{% endblock %}
{% block content %}
<form action="#" method="POST">
{{ form.as_p }}
<input type="submit" value="Speak!" />
</form>
{% endblock %}""")

@login_required
@get_or_post
def smoke_test_2(get, guts):
    if get:
        form = WrapperSmokeTestForm()
        return TemplateResponse(template, {"form": form})
    else:
        form = WrapperSmokeTestForm(guts.parameters)
        if form.is_valid():
            quux = form.cleaned_data["quux"]
        else:
            quux = "something is wrong"
        return TemplateResponse(template, {"form": form, "quux": quux})
