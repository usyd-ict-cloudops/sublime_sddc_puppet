
import sublime
from sublime_plugin import WindowCommand
import os.path as osp
import subprocess
# from sddc_common.workflow import get_config
from .utils import NotProjectCommandHelper, get_setting, expand_path

executable_path = sublime.executable_path()

if sublime.platform() == 'osx':
    app_path = executable_path[:executable_path.rfind(".app/")+5]
    executable_path = app_path+"Contents/SharedSupport/bin/subl"


def subl_command(*args, **kwargs):
    return subprocess.Popen((executable_path,)+args,**kwargs)


def get_project(project_name=None):
    if project_name is None:
        project_name = get_setting('puppet_primary_project')
    pfn = get_setting('puppet_projects',{}).get(project_name, get_setting('puppet_project'))
    return expand_path(pfn)


def project_exists(project_name=None):
    return osp.exists(get_project(project_name))


def is_project(window,project_name=None):
    return get_project(project_name)==window.project_file_name()


def open_project(project_name=None):
    project_file_name = get_project(project_name)
    window = {w.project_file_name():w for w in sublime.windows()}.get(project_file_name)
    if window:
        sublime.message_dialog('Puppet project already open')
    else:
        subl_command('--project',project_file_name)


class PuppetCoreProjectCommand(NotProjectCommandHelper,WindowCommand):

    def run(self, account=None, name=None, email=None, location=None, setup=False, defaults=False, state=None, project_name=None):
        if setup:
            project_file_name = get_project(project_name)
            account = get_setting('puppet_repo_account') if account is None else account
            location = project_file_name.rsplit('.',1)[0]
            cfg = get_config()
            if cfg:
                name = name if name else cfg[0]
                email = email if email else cfg[1]
            if defaults:
                if project_exists(project_name):
                    return sublime.error_dialog('Project already exists!\n'+get_project(project_name))

        open_project(project_name)


class PuppetProjectCommand(NotProjectCommandHelper,WindowCommand):

    def run(self, defaults=False, setup=False, state=None, project_name=None):
        self.window.run_command('puppet_core_project',args={
            'defaults': defaults,
            'setup': setup,
            'state': state,
            'project_name': project_name
            })

    def description(self, defaults=False, setup=False, state=None, project_name=None):
        return "Setup Puppet"+[""," with Defaults"][defaults] if setup else "Open Puppet"

    def is_enabled(self, defaults=False, setup=False, state=None, project_name=None):
        if self.is_puppet() or is_project(self.window,project_name):
            return False
        return bool(project_exists(project_name)) != bool(setup)

    def is_visible(self, defaults=False, setup=False, state=None, project_name=None):
        return self.is_enabled(defaults, setup, state, project_name)
