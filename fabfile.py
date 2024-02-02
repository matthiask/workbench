import fh_fablib as fl


fl.require("1.0.20240116")
fl.config.update(host="www-data@feinheit06.nine.ch")

environments = [
    fl.environment(
        "production",
        {
            "domain": "hangar.diebruchpiloten.com",
            "branch": "solomon",
            "remote": "production",
        },
        aliases=["p"],
    ),
]


ns = fl.Collection(*fl.GENERAL, *fl.NINE, *environments)
