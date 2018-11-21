from fabric.api import cd, env, local, run, task


env.forward_agent = True
env.hosts = ["www-data@feinheit06.nine.ch"]


@task
def check():
    local("venv/bin/flake8 .")


@task
def deploy():
    check()
    local("git push origin master")

    with cd("hangar.diebruchpiloten.com"):
        run("git fetch origin")
        run("git merge --ff-only origin/solomon")
        run('find . -name "*.pyc" -delete')
        run("venv/bin/pip install -r requirements.txt")
        run("venv/bin/python manage.py migrate")
        run("venv/bin/python manage.py collectstatic --noinput")
        run("systemctl --user restart gunicorn@hangar.diebruchpiloten.com.service")


@task
def pull_database():
    local("dropdb --if-exists workbench")
    local("createdb --encoding UTF8 workbench")
    local(
        'ssh www-data@feinheit06.nine.ch "source .profile && pg_dump -Ox'
        ' hangar_diebruchpiloten_com" | psql workbench'
    )


@task
def mm():
    local("venv/bin/python manage.py makemessages -a -i venv -i htmlcov")


@task
def cm():
    local("cd conf && ../venv/bin/python ../manage.py compilemessages")


@task
def update_requirements():
    local("rm -rf venv")
    local("python3 -m venv venv")
    local("venv/bin/pip install -U pip wheel")
    local("venv/bin/pip install -U -r requirements-to-freeze.txt")
    local("venv/bin/pip freeze -l > requirements.txt")
