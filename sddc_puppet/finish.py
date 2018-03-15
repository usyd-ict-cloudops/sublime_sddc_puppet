import os.path as osp
import sublime
from sublime_plugin import WindowCommand, TextCommand
from sddc_common import scm
from sddc_common.workflow import work_on, promote_for, finalize_for
from sddc_common.async import AsyncMacroRunner
from .utils import ContextCommandHelper, ProjectCommandHelper
from functools import partial


class PuppetCoreFinishCommand(ProjectCommandHelper,AsyncMacroRunner,WindowCommand):

    status_fmt = 'Finishing {0[repo].working_dir} branch {0[branch]}'

    def run(self, repo_path, branch, force=False, state=None):
        if not osp.exists(repo_path):
            return

        repo = scm.Repo(repo_path)
        if repo is None:
            return

        branches = scm.branch_names(repo)

        if branch not in branches:
            return

        self.run_command(state, repo=repo, branch=branch, force=force)

    def async_cmd(self, repo, branch, force, **args):

        finalize_for(repo, branch, force=force)


class PuppetFinishCommand(ContextCommandHelper,scm.RepoHelper,AsyncMacroRunner,TextCommand):
    def run(self, edit, force=False, state=None):
        repo = self.repo
        if repo is None:
            return

        branches = [b for b in scm.branch_names(repo) if b!='master']

        if not branches:
            return

        cmd_args = {
            'repo_path': repo.working_dir,
            'force': force,
            'state': state
        }

        def on_select(window, args, items, idx):
            if idx < 0:
                return
            window.run_command('puppet_core_finish',args=dict(branch=items[idx],**args))

        self.view.window().show_quick_panel(branches, partial(on_select, self.view.window(), cmd_args, branches))
