import fh_fablib as fl
from fh_fablib import Collection, Connection, Path, config, task


config.update(
    app="workbench",
    base=Path(__file__).parent,
    host="deploy@workbench.feinheit.ch",
    domain="workbench.feinheit.ch",
    branch="main",
    remote="production",
    installations=["fh", "dbpag", "bf", "test"],
)


@task
def check(c):
    c.run("venv/bin/flake8 .")
    c.run("yarn run check")


def _do_deploy(c, folder, rsync):
    with c.cd(folder):
        c.run("git checkout main")
        c.run("git fetch origin")
        c.run("git merge --ff-only origin/main")
        c.run('find . -name "*.pyc" -delete')
        c.run("venv/bin/pip install -U pip wheel setuptools")
        c.run("venv/bin/pip install -r requirements.txt")
        for wb in config.installations:
            c.run("DOTENV=.env/{} venv/bin/python manage.py migrate".format(wb))
    if rsync:
        c.local("rsync -avz --delete static/ {}:{}static".format(config.host, folder))
    with c.cd(folder):
        c.run(
            "DOTENV=.env/{} venv/bin/python manage.py collectstatic --noinput".format(
                config.installations[0]
            ),
        )


def _restart_all(c):
    for wb in config.installations:
        c.run("systemctl --user restart workbench@{}".format(wb), echo=True)


@task
def deploy(c):
    check(c)
    c.run("git push origin main")
    c.run("yarn run prod")
    with Connection(config.host) as c:
        _do_deploy(c, "www/workbench/", rsync=True)
        _restart_all(c)


@task
def deploy_code(c):
    check(c)
    c.run("git push origin main")
    with Connection(config.host) as c:
        _do_deploy(c, "www/workbench/", rsync=False)
        _restart_all(c)


@task
def pull_db(c, namespace):
    remote = {"fh": "workbench", "dbpag": "dbpag-workbench", "bf": "bf-workbench"}[
        namespace
    ]
    c.run("dropdb --if-exists workbench", warn=True)
    c.run("createdb workbench")
    c.run(
        'ssh -C root@workbench.feinheit.ch "sudo -u postgres pg_dump -Ox %s"'
        " | psql workbench" % remote,
    )


ns = Collection(*fl.GENERAL, check, deploy, deploy_code, pull_db)
