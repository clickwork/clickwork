from django import template

register = template.Library()

@register.filter
def as_hms(value):
    """Given a floating-point number of seconds, translates it to an
    HH:MM:SS string."""
    long_seconds = int(value)
    (long_minutes, seconds) = divmod(long_seconds, 60)
    (hours, minutes) = divmod(long_minutes, 60)
    return "%d:%02d:%02d" % (hours, minutes, seconds)
as_hms.is_safe = True
