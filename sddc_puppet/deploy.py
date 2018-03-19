
import os
import os.path as osp
import sublime
from sublime_plugin import TextCommand, WindowCommand, EventListener
from sddc_common.async import AsyncMacroRunner
from sddc_common.workflow import work_on, deploy_for
from .utils import ProjectCommandHelper, ContextCommandHelper, parse_target, get_work_on_params, find_yaml_key, noop
from functools import partial


SDDC_DEPLOY_VIEW_TITLE = "SDDC_DEPLOY_MSG"
SDDC_DEPLOY_VIEW_SYNTAX = 'Packages/SDDC Puppet/SDDC Deploy Message.tmLanguage'
SDDC_DEPLOY_TEMPLATE = """
# Please enter the commit message for your changes. Lines starting
# with '#' will be ignored, and an empty message aborts the commit.
"""

def create_deploy_template(cur_file, repo, all_files, include_untracked):
    repo.git.add(all=True)
    renames = {d.b_path:d.a_path for d in repo.index.diff(repo.head.commit,R=True).iter_change_type('R')}
    repo.git.reset('HEAD',q=True)
    if repo.is_dirty() or repo.untracked_files:
        if all_files:
            if include_untracked:
                repo.git.add(all=True)
            else:
                repo.git.add(update=True)
                repo.git.add(list(renames.keys()))
        else:
            repo.git.add([cur_file])
            if cur_file in renames:
                repo.git.add([renames[cur_file]])
    else:
        return
    status = repo.git.status()
    repo.git.reset('HEAD',q=True)
    return SDDC_DEPLOY_TEMPLATE+''.join('#'+l if l[:1]=='\t' else '# '+l for l in status.splitlines(True))


class PuppetDeploy(object):

    windows = {}


class PuppetCoreDeployCommand(ProjectCommandHelper,AsyncMacroRunner,WindowCommand):

    status_fmt = 'Deploying {0[repo].working_dir} on branch {0[repo].head.ref.name}'

    def run(self, message, repo_path=None, files=(), all_files=True, include_untracked=True, state=None):
        if message is None:
            return
        if repo_path is None:
            if all_files or not files or not osp.exists(files[0]):
                return
            repo = work_on(files[0],project_root=self.project_root)
        else:
            repo = work_on(repo_path,project_root=self.project_root)
        self.run_command(message=message,repo=repo,state=state,files=files,all_files=all_files,include_untracked=include_untracked)

    def async_cmd(self, message, repo, files=(), all_files=True, include_untracked=True, state=None,**args):
        print(repo.working_dir,message,files,all_files,include_untracked,state)
        # return
        deploy_for(repo, message, *files,all_files=all_files,untracked_files=include_untracked)


class PuppetDeployCommand(ContextCommandHelper,AsyncMacroRunner,TextCommand):
    def run(self, edit, all_files=True, include_untracked=True, state=None):
        # 1. determine what to commit and return if nothing
        cur_file = self.view.file_name()
        if cur_file is None or not osp.exists(cur_file):
            return
        repo = work_on(cur_file,**self.work_on_params)
        if repo is None:
            return

        # 2. Find repo_path
        repo_path = repo.working_dir
        cur_file = osp.relpath(cur_file,repo_path)

        # 3. Create commit template
        template = create_deploy_template(cur_file, repo, all_files, include_untracked)
        if template is None:
            return

        # 4. Trigger a commit message window

        view = self.find_view(sddc_view='deploy', git_repo=repo_path)
        if not view:
            view = self.window.new_file()
            view.set_name(SDDC_DEPLOY_VIEW_TITLE)
            view.set_syntax_file(SDDC_DEPLOY_VIEW_SYNTAX)
            view.set_scratch(True)

            view.settings().set('sddc_view', 'deploy')
            view.settings().set('git_repo', repo_path)

        # # view.settings().set('sddc_all', True if include_untracked else False if all_files else None)
        # view.settings().set('sddc_all', all_files)
        # view.settings().set('sddc_untracked', include_untracked)
        # view.settings().set('sddc_file', cur_file)
        # view.settings().set('sddc_state', state)

        PuppetDeploy.windows[view.id()] = (self.window,state,cur_file,all_files,include_untracked)
        self.window.focus_view(view)

        view.run_command('puppet_template', {'template': template})


class PuppetTemplateCommand(TextCommand):

    def is_visible(self):
        return False

    def run(self, edit, template=''):
        if self.view.size() > 0:
            self.view.erase(edit, sublime.Region(0, self.view.size()))
        self.view.insert(edit, 0, template)
        self.view.sel().clear()
        self.view.sel().add(sublime.Region(0))



class PuppetDeployEventListener(EventListener):

    def on_close(self, view):
        vs = view.settings()
        if vs.get('sddc_view') == 'deploy' and view.id() in PuppetDeploy.windows and vs.get('is_puppet'):
            message = view.substr(sublime.Region(0, view.size()))
            message = ''.join(l for l in message.splitlines(True) if l[:1]!='#')
            if not message.strip():
                print('Aborting commit due to blank error message')
                return
            window,state,cur_file,all_files,include_untracked = PuppetDeploy.windows[view.id()]
            repo_path = view.settings().get('git_repo')
            window.run_command('puppet_core_deploy', {
                'message': message, 
                'files': [cur_file],
                'all_files': all_files,
                'include_untracked': include_untracked,
                'repo_path': repo_path,
                'state': state})
