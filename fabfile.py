from fabric.api import *


env.forward_agent = True
env.hosts = ['deploy@ftool.feinheit.ch']


@task
def deploy():
    local('git push origin master')
    with cd('www/ftool/'):
        run('git checkout master')
        run('git pull')
        run('find . -name "*.pyc" -delete')
        run('venv/bin/pip install -r requirements/production.txt')
        run('venv/bin/python manage.py migrate')
        run('venv/bin/python manage.py collectstatic --noinput')
        run('sudo service www-ftool restart')
