
import os
import os.path as osp
import sublime
from sublime_plugin import TextCommand, WindowCommand, EventListener
from sddc_common.async import AsyncMacroRunner
from sddc_common.workflow import work_on, sync_for
from functools import partial


class PuppetCoreSyncCommand(ProjectCommandHelper,AsyncMacroRunner,WindowCommand):

    status_fmt = 'Syncing {0[repo].working_dir} on branch {0[repo].head.ref.name}'

    def run(self, repo_path, branch=None, state=None):
        if repo_path is None:
            return
        repo = work_on(repo_path,project_root=self.project_root)
        if repo is None:
            return

        self.run_command(repo=repo, branch=branch, state=state)

    def async_cmd(self, repo, branch=None, **args):
        sync_for(repo, branch)


class PuppetSyncCommand(ContextCommandHelper,AsyncMacroRunner,TextCommand):

    def run(self, repo_path=None, branch=None):
        if repo_path is None:
            repo_path = self.view.file_name()
            if not repo_path or not osp.exists(repo_path):
                repo_path = self.view.settings().get('sddc_repo')
                if not repo_path or not osp.exists(repo_path):
                    return
        self.window.run_command('puppet_core_sync',args={'repo_path':repo_path,'branch':branch})
