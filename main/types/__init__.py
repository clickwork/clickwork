from django.conf import settings
registered_types = settings.TASK_TYPES

type_list = {}
for type in registered_types: 
    mod = __import__('main.types.%s' % type, None, None, type)
    type = mod.get_type()
    type_list[type.name] = type
    
