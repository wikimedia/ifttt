from fabric.api import task, env, sudo, cd, shell_env, require, put
from functools import wraps

import os

env.use_ssh_config = True
env.shell = '/bin/bash -c'

STAGES = {
    'staging': {
        'hosts': ['ifttt-staging-01.ifttt.eqiad.wmflabs'],
        'local_config_file': './staging.cfg',
        'branch': 'master',
    },
    'production': {
        'hosts': ['ifttt-01.ifttt.eqiad.wmflabs'],
        'local_config_file': './production.cfg',
        'branch': 'master',
    },
}

SOURCE_DIR = '/srv/ifttt'
VENV_DIR = '/srv/ifttt/venv'
DEST_CONFIG_FILE = 'ifttt.cfg'


def sr(*cmd):
    """
    Sudo Run - Wraps a given command around sudo and runs it as the
    www-data user
    """
    with shell_env(HOME='/srv/ifttt'):
        return sudo(' '.join(cmd), user='www-data')


def set_stage(stage='staging'):
    """
    Sets the stage and populate the environment with the necessary
    config. Doing this allows accessing from anywhere stage related
    details by simply doing something like env.source_dir etc

    It also uses the values defined in the secrets directories
    to substitute the templatized config files for the db and web configs,
    and loads the final db, queue and web configs as strings into the
    environment
    """
    env.stage = stage
    for option, value in STAGES[env.stage].items():
        setattr(env, option, value)


def ensure_stage(fn):
    """
    Decorator to ensure the stage is set
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        # The require operation will abort if the key stage
        # is not set in the environment
        require('stage', provided_by=(staging, production,))
        return fn(*args, **kwargs)
    return wrapper


@task
def production():
    set_stage('production')


@task
def staging():
    set_stage('staging')


@task
@ensure_stage
def initialize_server():
    """
    Setup an initial deployment on a fresh host.
    """
    print 'Setting up the ' + env.stage + ' server'

    # Setup source directory and make www-data the owner
    sudo('mkdir -p ' + SOURCE_DIR)
    sudo('chown www-data:www-data ' + SOURCE_DIR)

    # Clone ifttt source
    clone_source_repo()

    # Sets up a virtualenv directory
    sr('mkdir', '-p', VENV_DIR)
    sr('virtualenv', '--python', 'python2', VENV_DIR)

    # Uploads the db and ifttt channel creds to the server
    upload_config()

    # Updates the virtualenv with latest requirements
    upgrade_dependencies()


@task
@ensure_stage
def deploy():
    """
    Deploys updated code to the web server
    """
    print 'Deploying to ' + env.stage

    # Updates current version of ifttt source
    update_source_repo()

    # Uploads the db and ifttt channel creds to the server
    upload_config()

    # Updates the virtualenv with latest requirements
    upgrade_dependencies()

    # Restart ifttt web service
    restart_ifttt()


@ensure_stage
def clone_source_repo():
    """
    Clone source repo at SOURCE_DIR
    """
    sr('mkdir', '-p', SOURCE_DIR)
    sr('chmod', '-R', '775', SOURCE_DIR)
    with cd('/'):
        sr('git', 'clone', 'https://github.com/wikimedia/ifttt.git',
           SOURCE_DIR)
    with cd(SOURCE_DIR):
        sr('git', 'checkout', env.branch)


@ensure_stage
def update_source_repo():
    """
    Update the ifttt source repo
    """
    print 'Updating ifttt source repo'
    with cd(SOURCE_DIR):
        sr('git', 'fetch', 'origin', env.branch)
        sr('git', 'reset', '--hard', 'FETCH_HEAD')


@ensure_stage
def upload_config():
    """
    Upload config to the remote host
    """
    print 'Uploading config files to remote host(s)'
    put(env.local_config_file, os.path.join(SOURCE_DIR, DEST_CONFIG_FILE),
        use_sudo=True)
    sudo("chown www-data:www-data " +
         os.path.join(SOURCE_DIR, DEST_CONFIG_FILE))


@ensure_stage
def upgrade_dependencies():
    """
    Installs upgraded versions of requirements (if applicable)
    """
    print 'Upgrading requirements'
    with cd(VENV_DIR):
        sr(VENV_DIR + '/bin/pip', 'install', '--upgrade', '-r',
            os.path.join(SOURCE_DIR, 'requirements.txt'))


@task
@ensure_stage
def restart_ifttt():
    """
    Restarts the ifttt web sersive
    """
    print 'Restarting ifttt'
    sudo('service uwsgi-ifttt restart')
