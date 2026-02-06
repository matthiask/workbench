import fh_fablib as fl


fl.require("1.0.20250710")
fl.config.update(
    app="workbench",
    domain="workbench.feinheit.ch",
    branch="main",
    remote="production",
    python="3.14",
)


@fl.task
def dev(ctx):
    backend = fl.random.randint(50000, 60000)
    fl._concurrently(
        ctx,
        [
            f"uv run manage.py runserver {backend}",
            f"PORT=8000 yarn run rspack serve --mode=development --env backend={backend}",
        ],
    )


@fl.task
def update(ctx):
    fl.run_local(ctx, "uv sync")
    fl.run_local(ctx, "uv run manage.py migrate")


@fl.task
def upgrade(ctx):
    venv = fl.config.base / ".venv"
    fl.run_local(ctx, f"rm -rf {venv}")
    fl.run_local(ctx, f"uv venv --python {fl.config.python}")
    fl.run_local(ctx, "uv lock --upgrade")
    fl.run_local(ctx, "uv run manage.py migrate")
    fl.run_local(ctx, "prek install -f")


ns = fl.Collection(*fl.GENERAL, dev, update, upgrade)
