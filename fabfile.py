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
    fl.check(ctx)
    fl.run(
        ctx,
        "yarn run prettier --list-different --no-semi --trailing-comma es5"
        ' "absences/**/*.*" "planning/**/*.*" "timer/**/*.*"',
    )
    fl.run(
        ctx,
        'yarn run eslint "absences/**/*.js" "planning/**/*.js" "timer/**/*.js"',
    )
    fl.run(
        ctx,
        "pipx run interrogate"
        " -e node_modules -e venv -v -f 99 --whitelist-regex 'test_.*'",
    )


@task
def fmt(ctx):
    fl.fmt(ctx)
    fl.run(
        ctx,
        "yarn run prettier --write --no-semi --trailing-comma es5"
        ' "absences/**/*.*" "planning/**/*.*" "timer/**/*.*"',
    )


@fl.task
def mm(ctx):
    fl.run(
        ctx,
        "venv/bin/python extract_gettext.py > conf/strings.js",
    )
    fl.mm(ctx)


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
    fl._check_branch(ctx)
    check(ctx)
    fl.run(ctx, "git push origin main")
    fl.run(ctx, "NODE_ENV=production yarn run webpack -p --bail")
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
def pull_db(ctx, installation="fh"):
    fl.run(ctx, "dropdb --if-exists workbench", warn=True)
    fl.run(ctx, "createdb workbench")
    with Connection(config.host) as conn:
        e = fl._srv_env(conn, f"www/workbench/.env/{installation}")
        srv_dsn = e("DATABASE_URL")
    fl.run(
        ctx,
        f'ssh -C {config.host} "pg_dump -Ox {srv_dsn}" | psql workbench',
    )


ns = Collection(*fl.GENERAL, check, deploy, deploy_code, fmt, mm, pull_db)
