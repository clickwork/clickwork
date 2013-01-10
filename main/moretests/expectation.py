"""Framework building on the Django unit tests to encapsulate 'expectations'."""
from django.core.urlresolvers import reverse, resolve
from django.test import TestCase
from django.test.client import Client
import simplejson as json
import sys
from urlparse import urlparse
from main.wrapper import Encoder

def abstract():
    """Function to work around (pre-2.6) Python's lack of abstract methods.
    (http://norvig.com/python-iaq.html)"""
    caller = inspect.getouterframes(inspect.currentframe())[1][3]
    raise NotImplementedError(caller + " must be implemented in subclass")

class Conditions(object):
    """Contains the conditions that are tested before and after an
    action is performed."""

    def __init__(self, preconditions, postconditions, invariants):
        """Each argument must be a sequence of functions.  Each
        function in `preconditions` must take a dict, and its return
        value is interpreted as a Boolean; truth indicates that the
        precondition was met.  Each function in `postconditions` must
        take two dicts, and its return value is interpreted as a
        Boolean, which is interpreted in the same way.  Each function
        in `invariants` must take a single dict, and its return value
        must do something sensible with the `==` operator; called with
        the same input before and after an operation, if the two
        values are equal, then the operation is considered a success.
        NONE OF THESE FUNCTIONS MAY MUTATE THEIR ARGUMENTS."""
        self.preconditions = preconditions
        self.postconditions = postconditions
        self.invariants = invariants

    def __add__(self, other):
        return Conditions((tuple(self.preconditions) + tuple(other.preconditions)),
                          (tuple(self.postconditions) + tuple(other.postconditions)),
                          (tuple(self.invariants) + tuple(other.invariants)))

    @classmethod
    def null(cls):
        """Create an object that imposes absolutely no conditions."""
        return cls((), (), ())

    @classmethod
    def pre(cls, precondition):
        """Create an object containing a single precondition."""
        return cls((precondition,), (), ())

    @classmethod
    def post(cls, postcondition):
        """Create an object containing a single postcondition."""
        return cls((), (postcondition,), ())

    @classmethod
    def inv(cls, invariant):
        """Create an object containing a single invariant."""
        return cls((), (), (invariant,))

    @classmethod
    def dump_contexts(cls):
        """Create an object that dumps the contexts to stderr but does
        not actually impose any conditions.  This is useful when
        developing a test if you are not sure what \"good\" outputs
        should look like."""
        def dc(input_context, output_context):
            print >>sys.stderr, ">>> IN", json.dumps(input_context, cls=Encoder, indent=2)
            print >>sys.stderr, "<<< OUT", json.dumps(output_context, cls=Encoder, indent=2)
            return True
        return cls((), (dc,), ())

    def check(self, test_case, input_context, callback):
        pre_failure_msg = "Precondition %s failed (context %r)"
        inv_failure_msg = "Invariant %s failed (context %r, %r --> %r)"
        post_failure_msg = "Postcondition %s failed (contexts %r and %r)"
        for f in self.preconditions:
            test_case.assertTrue(f(input_context),
                                  pre_failure_msg % \
                                     (f.__name__, input_context))
        invariant_initial_values = \
            [(f, f(input_context)) for f in self.invariants]
        output_context = callback(input_context)
        for (f, before) in invariant_initial_values:
            after = f(input_context)
            test_case.assertEquals(before, after,
                                   inv_failure_msg % \
                                       (f.__name__, input_context, before, after))
        for f in self.postconditions:
            test_case.assertTrue(f(input_context, output_context),
                                 post_failure_msg % \
                                     (f.__name__, input_context, output_context))
        return output_context

class AbstractExpectation(object):
    """Superclass for all classes that implement the `check` method."""

    def action(self, test_case):
        """Subclasses must override this method.  It must return a
        closure, which the `check` method can than call with the given
        context."""
        abstract()

    def __init__(self, conditions):
        self.conditions = conditions

    def check(self, test_case, input_context=None):
        """Find out if this expectation is met when the action is
        performed.  `test_case` is an instance of
        `django.test.TestCase or some subclass thereof; `context` is a
        dict representing invocation-specific details, such as the
        arguments to a query form."""
        if input_context == None:
            input_context = {}
        output_context = self.conditions.check(test_case, input_context, self.action(test_case))
        return output_context

class WebTarget(object):
    """Represents various attributes of a Web page that will be
    tested.  NOTE: to simulate uploading files, a value of the
    input_context may be an open filehandle.  This does not exactly
    play nicely with the other abstractions in the system; in
    particular, the functions in the Conditions object must not read
    this filehandle."""

    def invoke(self, test_case, input_context):
        """Use the Client object in `test_case` to call up the
        JSON-formatted version of the given page, test the
        HTTP-related metadata such as the status code, and return the
        JSON data to the caller."""
        ## make the pseudo-HTTP request and get the response
        data = dict(input_context) # copy the dict
        data["response_format"] = "json"
        if self.method == "GET":
            response = test_case.client.get(self.path, data,
                                            follow=(self.final_views is not None))
        elif self.method == "POST":
            response = test_case.client.post(self.path, data,
                                             follow=(self.final_views is not None))
        else:
            test_case.fail("Unhandled HTTP method %s" % self.method)
        ## check the status code
        status_code_failure_message = \
            "Status code %d not in {%s}; response content:\n%s" % \
            (response.status_code,
             ", ".join([str(s) for s in self.statuses]),
             response.content)
        if "Location" in response:
            status_code_failure_message += "\nLocation: %s" % response["Location"]
        test_case.assert_(response.status_code in self.statuses,
                          status_code_failure_message)
        ## if appropriate, check where we have been redirected to
        if self.final_views:
            test_case.assert_(response.redirect_chain,
                              "This page should have been a redirect")
            final_path, penultimate_status_code = response.redirect_chain[-1]
            final_view, final_args, final_kwargs = resolve(urlparse(final_path)[2])
            test_case.assert_(final_view in self.final_views,
                              "Redirect to %s unexpected" % final_path)
        ## unmarshal the JSON in the response and return it to the caller
        if response.content:
            return json.loads(response.content)
        elif response.status_code in (301, 302):
            return {"__redirected_to__": response["Location"]}
        else:
            return {}

    def __init__(self, method, view, args=None, kwargs=None,
                 statuses=(200,), final_views=None):
        """The `method` argument is an HTTP method.  The `view` is a
        Django view function, the name of a view function, or a URL
        pattern name.  `args` and `kwargs` are arguments to the view
        function (which will be reverse-interpreted to get the proper
        URL).  `statuses` is a tuple of acceptable HTTP statuses; if,
        for example, you expect a certain view to return a 'not found'
        status, this tuple should be `(404,)`.  If the page is
        expected to return a redirect or a chain of redirects, then
        `final_views` contains the views that may be invoked by the
        final redirection."""
        assert method in ("GET", "POST"), "Invalid method: %s" % method
        self.method = method
        self.path = reverse(view, args=args, kwargs=kwargs)
        self.statuses = statuses
        self.final_views = final_views

class ViewExpectation(AbstractExpectation):
    """Expected behavior for one view method being invoked by the Web
    client that returns a certain page."""

    def action(self, test_case):
        return lambda input_context: self.target.invoke(test_case, input_context)

    def __init__(self, conditions, target):
        """The `target` argument is a `WebTarget` object."""
        super(ViewExpectation, self).__init__(conditions)
        self.target = target

###
### a test of the test framework
###

def null_precondition(input_context):
    return True

def null_postcondition(input_context, output_context):
    return True

def null_invariant(input_context):
    return True

from main.views.base import about

class ExpectationSmokeTest(TestCase):
    def runTest(self):
        null_conditions = Conditions((null_precondition,),
                                     (null_postcondition,),
                                     (null_invariant,))
        ## The "about" view, unlike most, does not require a logged-in user.
        target_about = WebTarget("GET", about)
        expectation = ViewExpectation(null_conditions, target_about)
        expectation.check(self)
