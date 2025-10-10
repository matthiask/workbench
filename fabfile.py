import fh_fablib as fl


fl.require("1.0.20250710")
fl.config.update(
    app="workbench",
    domain="workbench.feinheit.ch",
    branch="main",
    remote="production",
    python="3.14",
)
ns = fl.Collection(*fl.GENERAL)
