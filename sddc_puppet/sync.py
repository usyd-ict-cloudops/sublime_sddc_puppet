
import os
import os.path as osp
import sublime
from sublime_plugin import TextCommand, WindowCommand
from sddc_common.async import AsyncMacroRunner
from sddc_common.workflow import work_on, sync_for
from sddc_common.scm import RepoHelper
from .utils import (ProjectCommandHelper, ContextCommandHelper)
from functools import partial


class PuppetCoreSyncCommand(ProjectCommandHelper,AsyncMacroRunner,WindowCommand):

    status_fmt = 'Syncing {0[repo].working_dir} on branch {0[repo].head.ref.name}'

    def run(self, repo_path, branch=None, state=None):
        print(repo_path,branch)
        if repo_path is None:
            return
        repo = work_on(repo_path,project_root=self.project_root)
        if repo is None:
            return

        self.run_command(repo=repo, branch=branch, state=state)

    def async_cmd(self, repo, branch=None, **args):
        sync_for(repo, branch)


class PuppetSyncCommand(ContextCommandHelper,RepoHelper,AsyncMacroRunner,TextCommand):

    def run(self, edit, repo_path=None, branch=None):
        if repo_path is None:
            repo = self.repo
            if repo:
                repo_path = repo.working_dir
        if not repo_path:
            return
        self.window.run_command('puppet_core_sync', args={
            'repo_path': repo_path,
            'branch': branch,
            'state': None
        })
