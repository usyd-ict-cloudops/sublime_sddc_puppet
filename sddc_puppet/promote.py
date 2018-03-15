import sublime
from sublime_plugin import WindowCommand, TextCommand
from sddc_common import scm
from sddc_common.workflow import work_on, promote_for, promote_to
from sddc_common.async import AsyncMacroRunner
from .utils import get_promote_targets, ContextCommandHelper, ProjectCommandHelper
from functools import partial


def merged_into(repo,branch):
    return [h.name for h in repo.heads if len(h.commit.parents) > 1 and repo.heads[branch].commit in h.commit.parents]


class PuppetCorePromoteCommand(ProjectCommandHelper,AsyncMacroRunner,WindowCommand):

    status_fmt = 'Promoting {0[repo].working_dir} on branch {0[repo].head.ref.name} with branch {0[branch]}'

    def run(self, repo_path, branch, finalize=False, force=False, force_finalize=False, overwrite=True, to=None, state=None):
        repo = scm.Repo(repo_path)
        if repo is None:
            return

        if to is not True and to is not False:
            return

        self.run_command(state=state, repo=repo, branch=branch, 
            finalize=finalize, force=force, force_finalize=force_finalize, 
            overwrite=overwrite, to=to)

    def async_cmd(self, repo, branch, finalize, force, force_finalize, overwrite, to, **args):
        if to:
            promote_to(repo, branch, finalize, force, force_finalize, overwrite)
        else:
            promote_for(repo, branch, finalize, force, force_finalize, overwrite)


class PuppetPromoteCommand(ContextCommandHelper,scm.RepoHelper,AsyncMacroRunner,TextCommand):
    def run(self, edit, finalize=False, force=False, force_finalize=False, overwrite=True, to=None, state=None):
        repo = self.repo
        if repo is None:
            return

        to_targets = [[t,'Target'] for t in get_promote_targets(repo.head.ref.name, is_src=True)]
        from_targets = [[t,'Source'] for t in get_promote_targets(repo.head.ref.name, is_src=False)]

        if to is None:
            items = to_targets + from_targets
        elif to is True:
            items = to_targets
        elif to is False:
            items = from_targets
        else:
            return

        branches = scm.branch_names(repo)

        items = [i for i in items if i[0] in branches]

        args = {
            'repo_path': repo.working_dir,
            'finalize': finalize,
            'force': force,
            'force_finalize': force_finalize,
            'overwrite': overwrite,
            'state': state
        }

        def on_select(window, args, items, idx):
            if idx < 0:
                return
            window.run_command('puppet_core_promote',args=dict(branch=items[idx][0],**args))

        self.view.window().show_quick_panel(items, partial(on_select, self.view.window(), args, items))
