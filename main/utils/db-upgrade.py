#!/usr/bin/python

import optparse
import simplejson
import subprocess
import sys
import os

djangopath = os.path.join(os.path.dirname(sys.argv[0]),"../../")
os.environ['DJANGO_SETTINGS_MODULE'] = "settings"
sys.path.extend(["/usr/local/lib/python2.6/dist-packages/",djangopath])

from django.db import transaction
from local_settings import BASE_PATH, DATABASES
from main.models import Version

def apply_upgrade(filename):
    full_path = os.path.join(BASE_PATH, "main/utils", filename)
    subprocess.check_call(["psql", DATABASES['default']['NAME'], "-f", full_path])

def get_version():
    db_version = ""
    try:
        sid = transaction.savepoint()
        db_versions = Version.objects.order_by("-version")
        if db_versions.count() == 0:
            db_version = ""
        else:
            db_version = db_versions[0].version
    except:
        transaction.savepoint_rollback(sid)
    return db_version

if __name__ == "__main__":
        parser = optparse.OptionParser()
        parser.add_option("-t", "--test", dest="test", action="store_true",
                          help="test to see if an upgrade is needed")

        (options, args) = parser.parse_args()

        upgrade_path = simplejson.load(open(os.path.join(BASE_PATH,
				"main/utils/upgrades-manifest.json")))["upgrade_path"]

        db_version = get_version()

        while upgrade_path.has_key(str(db_version)):
            if options.test:
                # If we need an upgrade and we are just asking, yell
                sys.exit("1")

            #If we are told to upgrade do it
            else:
                while upgrade_path.has_key(str(db_version)):
                    for upgrade in upgrade_path[str(db_version)]:
                        print "DB Version %s, applying %s to upgrade" % (db_version, upgrade)
                        apply_upgrade(upgrade)
                    if db_version == "":
                        db_version = 0
                    Version(version = db_version + 1).save() 
                    new_version = get_version()
                    if new_version == db_version:
                        print "Upgrade from %s failed" % db_version
                        sys.exit(1)
                    db_version = new_version
	print "Database now v%s" % db_version

            
        
