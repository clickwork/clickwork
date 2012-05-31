from django.contrib.sites.models import Site
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.shortcuts import render_to_response
from django.http import HttpResponseRedirect
from django.conf import settings 
from django.template.loader import get_template
from django.core.mail import send_mail

import re

try:
    import django.newforms as forms
except ImportError:    
    import django.forms as forms

from main.wrapper import get_or_post, ViewResponse, TemplateResponse, ForbiddenResponse
import main.views.base

class NewUserForm(forms.Form):
    username = forms.CharField(max_length=30, required=False)
    first_name = forms.CharField(max_length=30)
    last_name = forms.CharField(max_length=30)
    email = forms.CharField(max_length=50)

class ChangePassForm(forms.Form):
    old_pass = forms.CharField(label="Old Password", widget=forms.PasswordInput())
    pass1 = forms.CharField(label="New Password", widget=forms.PasswordInput())
    pass2 = forms.CharField(label="New Password (again)", widget=forms.PasswordInput())


@login_required
@get_or_post
def change_password(get, guts):
    message = ""
    if get:
        f = ChangePassForm()
    else:
        f = ChangePassForm(guts.parameters)
        if f.is_valid():
            cleaned = f.cleaned_data
            if guts.user.check_password(cleaned['old_pass']) and cleaned['pass1'] == cleaned['pass2']:
                guts.user.set_password(cleaned['pass1'])
                guts.user.save()
                return ViewResponse(main.views.base.home)
            elif not guts.user.check_password(cleaned['old_pass']):
                message = "You did not enter your current password correctly"
            else:
                message = "Passwords didn't match."
    template = get_template("change_password.html")
    return TemplateResponse(template, {'form':f, 'user': guts.user, 'message': message})

@login_required
@get_or_post
def new_user(get, guts):
    if get:
        template = get_template("new_user.html")
        return TemplateResponse(template, {"form": NewUserForm()})
    else:
        if not guts.user.is_superuser:
            return ForbiddenResponse("Only administrators may create new accounts.")
        f = NewUserForm(guts.parameters)
        if f.is_valid():
            frm = settings.EMAIL_FROM
            current_site = Site.objects.get_current()
            subject = "New %s Account Created" % current_site.name
            base = "https://%s" % current_site.domain 

            cleaned = f.cleaned_data
            password = User.objects.make_random_password()
            if cleaned["username"]:
                username = cleaned["username"]
            else:
                ## peel off the part before the @
                ## and then translate non-alpha-numeric characters to underscores
                username = re.sub(r'\W', '_', cleaned["email"].split("@", 1)[0])
            u = User.objects.create_user(username, cleaned["email"], password)
            u.first_name = cleaned["first_name"]
            u.last_name = cleaned["last_name"]
            u.save()

            send_mail(subject, """An account has been created for you on the %s system.

Login information:

    Username: %s
    Password: %s

Login to change your password:

    %s/user_management/

If you have any problems logging in, please email us for assistance at:

  %s

    """ % (current_site.name, username, password, base, frm), frm, [cleaned['email']]) 

            u.save()
            template = get_template("new_user_created.html")
            return TemplateResponse(template, {'username': username, 'password': password})
        else:    
            template = get_template("new_user.html")
            return TemplateResponse("new_user.html", {'form': NewUserForm()})
