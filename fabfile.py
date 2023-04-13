import fh_fablib as fl


fl.require("1.0.20230411")
fl.config.update(
    app="workbench",
    base=fl.Path(__file__).parent,
    host="deploy@workbench.feinheit.ch",
    domain="workbench.feinheit.ch",
    branch="main",
    remote="production",
    installations=["fh", "dbpag", "bf", "test"],
)


def _do_deploy(conn, folder, rsync):
    with conn.cd(folder):
        fl.run(conn, "git checkout main")
        fl.run(conn, "git fetch origin")
        fl.run(conn, "git reset --hard origin/main")
        fl.run(conn, 'find . -name "*.pyc" -delete')
        fl.run(conn, "venv/bin/pip install -U 'pip!=20.3.2' wheel setuptools")
        fl.run(conn, "venv/bin/pip install -r requirements.txt")
        for wb in fl.config.installations:
            fl.run(conn, f"DOTENV=.env/{wb} venv/bin/python manage.py migrate")
    if rsync:
        conn.local(f"rsync -avz --delete static/ {fl.config.host}:{folder}static")
    with conn.cd(folder):
        fl.run(
            conn,
            "DOTENV=.env/{} venv/bin/python manage.py collectstatic --noinput".format(
                fl.config.installations[0]
            ),
        )


def _restart_all(conn):
    for wb in fl.config.installations:
        fl.run(conn, f"systemctl --user restart workbench@{wb}", echo=True)


@fl.task
def deploy(ctx):
    fl._check_branch(ctx)
    fl.run(ctx, "git push origin main")
    fl.run(ctx, "NODE_ENV=production yarn run webpack -p --bail")
    with fl.Connection(fl.config.host) as conn:
        _do_deploy(conn, "www/workbench/", rsync=True)
        _restart_all(conn)
    fl.fetch(ctx)


@fl.task
def deploy_code(ctx):
    fl.run(ctx, "git push origin main")
    with fl.Connection(fl.config.host) as conn:
        _do_deploy(conn, "www/workbench/", rsync=False)
        _restart_all(conn)
    fl.fetch(ctx)


@fl.task
def pull_db(ctx, installation="fh"):
    fl.run(ctx, "dropdb --if-exists workbench", warn=True)
    fl.run(ctx, "createdb workbench")
    with fl.Connection(fl.config.host) as conn:
        e = fl._srv_env(conn, f"www/workbench/.env/{installation}")
        srv_dsn = e("DATABASE_URL")
    fl.run(
        ctx,
        f'ssh -C {fl.config.host} "pg_dump -Ox {srv_dsn}" | psql workbench',
    )


@fl.task
def dev(ctx):
    fl._old_dev(ctx)


ns = fl.Collection(*fl.GENERAL, deploy, deploy_code, dev, pull_db)
