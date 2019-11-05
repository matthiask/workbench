from fabric.api import env, local, task
from fabric.contrib.project import rsync_project


env.hosts = ["deploy@workbench.feinheit.ch"]


@task
def deploy():
    local("yarn run build")
    rsync_project(
        local_dir="dist/",
        remote_dir="www/workbench/htdocs/timerr/",
        delete=True,
    )
