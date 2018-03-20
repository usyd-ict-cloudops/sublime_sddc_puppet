
import sublime
import sublime_plugin
import os
import os.path as osp
import json
import subprocess
from sddc_common.workflow import get_config, set_config
from .utils import NotProjectCommandHelper, ProjectCommandHelper, get_setting, expand_path, parse_target

def get_executable_path():
    executable_path = sublime.executable_path()
    if sublime.platform() == 'osx':
        app_path = executable_path[:executable_path.rfind(".app/")+5]
        executable_path = app_path+"Contents/SharedSupport/bin/subl"
    return executable_path


def subl_command(*args, **kwargs):
    return subprocess.Popen((get_executable_path(),)+args,**kwargs)


def get_project(project_name=None):
    if project_name is None:
        project_name = get_setting('puppet_primary_project')
    pfn = get_setting('puppet_projects',{}).get(project_name, get_setting('puppet_project'))
    return expand_path(pfn) if pfn else None


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


class PuppetCoreProjectCommand(NotProjectCommandHelper,sublime_plugin.WindowCommand):

    def run(self, account=None, name=None, email=None, location=None, setup=False, defaults=False, state=None, project_name=None):
        if setup:
            project_file_name = get_project(project_name)
            account = get_setting('puppet_scm_provider_account') if account is None else account
            targets = get_setting('puppet_ensure_targets',[])
            location = osp.dirname(project_file_name)
            cfg = get_config()
            if cfg:
                name = name if name else cfg[0]
                email = email if email else cfg[1]
            if defaults:
                if project_exists(project_name):
                    return sublime.error_dialog('Project already exists!\n'+get_project(project_name))
                if not osp.exists(location):
                    os.makedirs(location)
                    with open(project_file_name,'w') as fp:
                        json.dump({'folders': [{
                                'path': '.', "file_exclude_patterns": ["*.sublime-project"]}
                            ], 'settings': {'is_puppet': True, 'puppet_ensure_targets': targets,
                            'puppet_scm_provider_account': account}},fp,indent=4)
            else:
                sublime.error_dialog('Setup Puppet with custom options not available at this time.')
                return
            
            if targets and isinstance(targets, list):
                sublime.set_timeout(self.ensure_targets,5000)

        open_project(project_name)

    def ensure_targets(self):
        for w in sublime.windows():
            w.run_command('puppet_project_ensure_targets')


class PuppetProjectCommand(NotProjectCommandHelper,sublime_plugin.WindowCommand):

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


class PuppetProjectEnsureTargetsCommand(ProjectCommandHelper,sublime_plugin.WindowCommand):

    def run(self):
        print('Ensuring Puppet Targets')
        targets = self.get_setting('puppet_ensure_targets',[])
        if not targets or not isinstance(targets, list):
            return
        for target in targets:
            t_obj = parse_target(target)
            if t_obj is not None:
                repo_path = osp.join(self.project_root,t_obj.repo)
                if not osp.exists(repo_path):
                    self.window.run_command('puppet_core_work_on',args={"target":target})
                else:
                    print('Exists', repo_path)
