import fh_fablib as fl


fl.require("1.0.20241002")
fl.config.update(
    app="workbench", domain="workbench.feinheit.ch", branch="main", remote="production"
)


@fl.task
def dev(ctx):
    fl._old_dev(ctx)


ns = fl.Collection(*fl.GENERAL, dev)
