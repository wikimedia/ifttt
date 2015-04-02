from fabric.api import task, env, sudo, cd

tool_name = 'ifttt'

env.hosts = ['tools-login.wmflabs.org']
env.sudo_user = 'tools.{}'.format(tool_name)
env.sudo_prefix = 'sudo -ni '
env.use_ssh_config = True

home_dir = '/data/project/{}'.format(tool_name)
code_dir = '{}/www/python/src'.format(home_dir)


@task
def deploy(*args):
    with cd(code_dir):
        sudo('git rev-list HEAD --max-count=1')
        sudo('git fetch')
        sudo('git reset --hard origin/master')
        sudo('webservice uwsgi-python restart')
