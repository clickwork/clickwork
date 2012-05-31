#!/usr/bin/python
import sys, os
import syslog

try:

    import time
    import daemon
    import pwd

    import pid

    djangopath = os.path.join(os.path.dirname(sys.argv[0]),"../../")
    sys.path.append(djangopath)
    os.environ['DJANGO_SETTINGS_MODULE'] = "settings"

    from main.models import Project, Task, ProjectUpload 
    from main.types import type_list
    import traceback
    from django.db import transaction

except Exception, e :
    syslog.syslog(syslog.LOG_ERR, "Failed importing %s" % e)
    raise e

@transaction.commit_on_success
def run_upload(upload):
    upload_type = upload.project.type
    type = type_list[upload_type]
    project = type.cast(upload.project)
    if project.handle_input:
        project.handle_input(upload)

def check_uploads():
    pu = ProjectUpload.objects.filter(complete=False)
    if pu.count():
        upload = pu[0]
        print "Running %s" % upload.id
        error = None
        try:
            run_upload(upload)
        except Exception, E:
            tb = "".join(traceback.format_tb(sys.exc_traceback))
            error = "Exception Type: %s, Text: %s\nTraceback:\n%s" % (type(E), str(E), tb)    
        upload.complete = True
        if error:
            syslog.syslog(syslog.LOG_ERR, error)
            upload.error = error
        upload.full_clean()
        upload.save()
        
        print "Done %s" % upload.id

def main_loop():
    while True:
        check_uploads()
        time.sleep(10)
                        

if __name__ == "__main__":
    try:
        assert os.getuid() == 0, "Must be run as root"
        #is there something better here?
        apache = pwd.getpwnam('apache')
        #make a pid, run as apache
        context = daemon.DaemonContext(
            working_directory='/usr/lib/clickwork/',
            umask=0o002,
            pidfile=pid.PidFile('/var/run/taskfactory/pid'),
            uid=apache[2],
            gid=apache[3]
            )

        with context:
            main_loop()
    except Exception, e:
        syslog.syslog(syslog.LOG_ERR, "Unhandled Exception %s - Died" % e)
        raise e
