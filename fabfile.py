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
def check(ctx):
    ctx.run("venv/bin/flake8 .")
    ctx.run("yarn run check")


def _do_deploy(conn, folder, rsync):
    with conn.cd(folder):
        conn.run("git checkout main")
        conn.run("git fetch origin")
        conn.run("git merge --ff-only origin/main")
        conn.run('find . -name "*.pyc" -delete')
        conn.run("venv/bin/pip install -U pip wheel setuptools")
        conn.run("venv/bin/pip install -r requirements.txt")
        for wb in config.installations:
            conn.run("DOTENV=.env/{} venv/bin/python manage.py migrate".format(wb))
    if rsync:
        conn.local(
            "rsync -avz --delete static/ {}:{}static".format(config.host, folder)
        )
    with conn.cd(folder):
        conn.run(
            "DOTENV=.env/{} venv/bin/python manage.py collectstatic --noinput".format(
                config.installations[0]
            ),
        )


def _restart_all(conn):
    for wb in config.installations:
        conn.run("systemctl --user restart workbench@{}".format(wb), echo=True)


@task
def deploy(ctx):
    check(ctx)
    ctx.run("git push origin main")
    ctx.run("yarn run prod")
    with Connection(config.host) as conn:
        _do_deploy(conn, "www/workbench/", rsync=True)
        _restart_all(conn)
    fl.fetch(ctx)


@task
def deploy_code(ctx):
    check(ctx)
    ctx.run("git push origin main")
    with Connection(config.host) as conn:
        _do_deploy(conn, "www/workbench/", rsync=False)
        _restart_all(conn)
    fl.fetch(ctx)


@task
def pull_db(ctx, namespace):
    remote = {"fh": "workbench", "dbpag": "dbpag-workbench", "bf": "bf-workbench"}[
        namespace
    ]
    ctx.run("dropdb --if-exists workbench", warn=True)
    ctx.run("createdb workbench")
    ctx.run(
        'ssh -C root@workbench.feinheit.ch "sudo -u postgres pg_dump -Ox %s"'
        " | psql workbench" % remote,
    )


ns = Collection(*fl.GENERAL, check, deploy, deploy_code, pull_db)
