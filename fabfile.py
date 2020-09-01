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
    fl.run(ctx, "pipx run --spec 'flake8>=3.8.3' flake8 .")
    fl.run(ctx, "yarn run check")


def _do_deploy(conn, folder, rsync):
    with conn.cd(folder):
        fl.run(conn, "git checkout main")
        fl.run(conn, "git fetch origin")
        fl.run(conn, "git merge --ff-only origin/main")
        fl.run(conn, 'find . -name "*.pyc" -delete')
        fl.run(conn, "venv/bin/pip install -U pip wheel setuptools")
        fl.run(conn, "venv/bin/pip install -r requirements.txt")
        for wb in config.installations:
            fl.run(conn, "DOTENV=.env/{} venv/bin/python manage.py migrate".format(wb))
    if rsync:
        conn.local(
            "rsync -avz --delete static/ {}:{}static".format(config.host, folder)
        )
    with conn.cd(folder):
        fl.run(
            conn,
            "DOTENV=.env/{} venv/bin/python manage.py collectstatic --noinput".format(
                config.installations[0]
            ),
        )


def _restart_all(conn):
    for wb in config.installations:
        fl.run(conn, "systemctl --user restart workbench@{}".format(wb), echo=True)


@task
def deploy(ctx):
    check(ctx)
    fl.run(ctx, "git push origin main")
    fl.run(ctx, "yarn run prod")
    with Connection(config.host) as conn:
        _do_deploy(conn, "www/workbench/", rsync=True)
        _restart_all(conn)
    fl.fetch(ctx)


@task
def deploy_code(ctx):
    check(ctx)
    fl.run(ctx, "git push origin main")
    with Connection(config.host) as conn:
        _do_deploy(conn, "www/workbench/", rsync=False)
        _restart_all(conn)
    fl.fetch(ctx)


@task
def pull_db(ctx, namespace):
    remote = {"fh": "workbench", "dbpag": "dbpag-workbench", "bf": "bf-workbench"}[
        namespace
    ]
    fl.run(ctx, "dropdb --if-exists workbench", warn=True)
    fl.run(ctx, "createdb workbench")
    fl.run(
        ctx,
        'ssh -C root@workbench.feinheit.ch "sudo -u postgres pg_dump -Ox %s"'
        " | psql workbench" % remote,
    )


ns = Collection(*fl.GENERAL, check, deploy, deploy_code, pull_db)
