from fabric.api import cd, env, execute, local, run, task


env.forward_agent = True
env.hosts = ["deploy@workbench.feinheit.ch"]


@task
def check():
    local("venv/bin/flake8 .")


@task
def deploy():
    check()
    local("git push origin master")

    with cd("www/workbench/"):
        run("git checkout master")
        run("git fetch origin")
        run("git merge --ff-only origin/master")
        run('find . -name "*.pyc" -delete')
        run("venv/bin/pip install -r requirements.txt")
        run("venv/bin/python manage.py migrate")
        run("venv/bin/python manage.py collectstatic --noinput")
        run("sudo systemctl restart workbench.service")

    # with cd("www/dbpag-workbench/"):
    #     run("git checkout master")
    #     run("git fetch origin")
    #     run("git merge --ff-only origin/master")
    #     run('find . -name "*.pyc" -delete')
    #     run("venv/bin/pip install -r requirements.txt")
    #     run("venv/bin/python manage.py migrate")
    #     run("venv/bin/python manage.py collectstatic --noinput")
    #     run("sudo systemctl restart dbpag-workbench.service")


@task
def pull_database(namespace):
    remote = {"fh": "workbench", "dbpag": "dbpag-workbench"}[namespace]

    local("dropdb --if-exists workbench")
    local("createdb --encoding UTF8 workbench")
    local(
        'ssh root@workbench.feinheit.ch "sudo -u postgres pg_dump -Ox %s"'
        " | psql workbench" % remote
    )


@task(alias="mm")
def makemessages():
    local("venv/bin/python manage.py makemessages -a -i venv -i htmlcov")


@task(alias="cm")
def compilemessages():
    local("cd conf && ../venv/bin/python ../manage.py compilemessages")


@task
def update_requirements():
    local("rm -rf venv")
    local("python3 -m venv venv")
    local("venv/bin/pip install -U pip wheel")
    local("venv/bin/pip install -U -r requirements-to-freeze.txt")
    execute("freeze")


@task
def freeze():
    local("venv/bin/pip freeze -l > requirements.txt")
