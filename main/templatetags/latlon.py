from django import template

register = template.Library()

def as_dms(f_degrees):
    """Given a floating-point number of degrees, translates it to
    degrees, minutes, and seconds."""
    degrees = int(f_degrees)
    degrees_fraction = f_degrees - degrees
    f_minutes = degrees_fraction * 60
    minutes = int(f_minutes)
    minutes_fraction = f_minutes - minutes
    f_seconds = minutes_fraction * 60
    seconds = int(f_seconds)
    return u"%d\u00b0%02d'%02d\"" % (degrees, minutes, seconds)

@register.filter
def lat(f_degrees):
    abs_degrees = abs(f_degrees)
    sign = int(f_degrees / abs_degrees)
    return as_dms(abs_degrees) + ["", "N", "S"][sign]
lat.is_safe = True

@register.filter
def lon(f_degrees):
    abs_degrees = abs(f_degrees)
    sign = int(f_degrees / abs_degrees)
    return as_dms(abs_degrees) + ["", "E", "W"][sign]
lon.is_safe = True
