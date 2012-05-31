# -*- coding: utf-8 -*-
# -*- encoding: utf-8 -*-

from django import template
from django.utils.html import conditional_escape
from django.utils.safestring import mark_safe
import urllib
import re
register = template.Library()

def fancyurlize(match):
    length = 5
    text = match.group(0)
    end_text = []
    while True:
        if text[-1] in ('.', ';', ')', ','):
            end_text.append(text[-1])
            text = text[:-1]
        else:
            break
    end_text.reverse()
    end_text = "".join(end_text)
    value = text
    extra = False
    for char in (u'?'):
        arr = value.split(char)
        if len(arr) > 1:
            text = arr[0]
            extra = True

    if len(text) > length:
        arr = re.split(r'(?<!/)/(?!/)', text)
        if len(arr) > 2:
            text = u'/'.join((arr[0], u'...', arr[-1]))

    if len(text) > 0 and text[-1] != u'/':
        text = u''.join((text))
    if extra:
        text = "%s?..." % text
    try:
        text = urllib.unquote(text).encode("latin-1")
    except Exception:    
        text = urllib.unquote(text).encode("utf-8")
    return_value = u'<a href="%s" target="_blank">%s</a>%s' % (
        conditional_escape(value),
        conditional_escape(text),
        end_text
    )
    return mark_safe(return_value)

fancyurlize.is_safe = True

@register.filter
def urlfilter(value):
    try:
        value = re.sub(r'((((ht|f)tp(s?))\://){1}[^\s)]+)', fancyurlize, value)
    except:
        # We want to fail in a way that value is passed through unchanged.
        pass
    return mark_safe(value)

test_cases = [
    ('This is a furniture store (http://www.moebel-fundgrube.de/)(http://www.moebel-fundgrube.de/kh.html).', 'This is a furniture store (<a href="http://www.moebel-fundgrube.de/" target="_blank">http://www.moebel-fundgrube.de/</a>)(<a href="http://www.moebel-fundgrube.de/kh.html" target="_blank">http://www.moebel-fundgrube.de/kh.html</a>).'),
    ('http://crschmidt.net/', '<a href="http://crschmidt.net/" target="_blank">http://crschmidt.net/</a>'),
    ('(http://www.maropeng.co.za/)(http://en.wikipedia.org/wiki/Cradle_of_Humankind)', '(<a href="http://www.maropeng.co.za/" target="_blank">http://www.maropeng.co.za/</a>)(<a href="http://en.wikipedia.org/wiki/Cradle_of_Humankind" target="_blank">http://en.wikipedia.org/.../Cradle_of_Humankind</a>)'),
    ('Foobar', 'Foobar')
]   
if __name__ == "__main__":
    for i in test_cases:
        if urlfilter(i[0]) == i[1]:
            print "Pass"
        else:
            val = urlfilter(i[0])
            print "Fail: Got: %s\n--\nExpected: %s" % (val, i[1])
