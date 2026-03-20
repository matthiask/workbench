import fh_fablib as fl


fl.require("1.0.20260320")
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


ns = fl.Collection(*fl.GENERAL, dev)
