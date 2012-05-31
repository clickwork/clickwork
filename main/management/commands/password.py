from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User

class Command(BaseCommand):
    args = '<user> <password>'
    help = 'Set a password from the command line'
    
    def handle(self, *args, **options):
        user = None
        try:
            user = User.objects.get(username__exact = args[0])
        except User.DoesNotExist:
            raise CommandError('User "%s" does not exist' % args[0])

        user.set_password(args[1])
        user.save()
        self.stdout.write('Successfully changed password of "%s"\n' % args[0])
