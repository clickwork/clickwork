git checkout open-source
git archive --format=tar --prefix=clickwork-v1.1.0-open-source-fork/ open-source | bzip2 -9 > clickwork-v1.1.0-open-source-fork.tar.bz2
scp clickwork-v1.1.0-open-source-fork.tar.bz2  user@test-server:
ssh user@test-server
sudo aptitude install postgresql-9.1 postgresql-client-9.1
sudo aptitude install python2.7-psycopg2 python-markdown
sudo -u postgres createuser user
createdb default_db
mv clickwork-v1.1.0-open-source-fork clickwork
cd clickwork/third/Django-1.3.1/
sudo python setup.py install
cd ../..
python manage.py syncdb
python manage.py runserver 0.0.0.0:8080
