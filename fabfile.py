import fh_fablib as fl


fl.require("1.0.20250408")
fl.config.update(
    app="workbench", domain="workbench.feinheit.ch", branch="main", remote="production"
)
ns = fl.Collection(*fl.GENERAL)
