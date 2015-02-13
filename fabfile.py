from fabric.api import cd, env, local, run, task


env.forward_agent = True
env.hosts = ['deploy@ftool.feinheit.ch']


@task
def deploy():
    local('flake8 .')
    local('git push origin master')
    with cd('www/ftool/'):
        run('git checkout master')
        run('git pull')
        run('find . -name "*.pyc" -delete')
        run('venv/bin/pip install -r requirements/production.txt')
        run('venv/bin/python manage.py migrate')
        run('venv/bin/python manage.py collectstatic --noinput')
        run('sudo service www-ftool restart')


@task
def pull_database():
    local('dropdb --if-exists ftool')
    local('createdb --encoding UTF8 ftool')
    local(
        'ssh root@ftool.feinheit.ch "sudo -u postgres pg_dump ftool'
        ' --no-privileges --no-owner --no-reconnect"'
        ' | psql ftool')
