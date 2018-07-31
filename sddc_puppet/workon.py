import os
import os.path as osp
import sublime
from sublime_plugin import WindowCommand, TextCommand, EventListener
from sddc_common import scm
from sddc_common.async import AsyncMacroRunner
from sddc_common.workflow import work_on, switch_to
from .utils import (ProjectCommandHelper, ContextCommandHelper, parse_target, get_work_on_params, 
    goto_yaml_key, noop, get_modules, get_module_branches)
from functools import partial


class PuppetCoreWorkOnCommand(ProjectCommandHelper,AsyncMacroRunner,WindowCommand):

    status_fmt = 'Getting {0[target].path}'

    def run(self, target=None, title='Work On', default_text='', state=None):
        if target:
            self.on_target(target,state=state)
        elif target is None:
            self.window.show_input_panel(title, default_text, partial(self.on_target,state=state), noop, noop)

    def on_target(self, target, state=None):
        '''path, branch=None, acct=None, project_root=None, rewrite_map=None, provider=None, url_fmt=None, off_branch=None'''
        if osp.exists(target):
            if not osp.isdir(target):
                self.window.open_file(target)
            return

        target = parse_target(target)

        if target is None:
            return

        print(target)

        self.run_command(state=state,target=target)

    def async_cmd(self, target, open_target=True, **args):
        '''
        Get a repo and open the needed file based on a target ref

        ref: #?[*^]?<prefix>(|<aertype>|~<quick>|_<name>)(|@<branch>)(|/|:<subpath>)

        '''
        work_on_params = get_work_on_params(self.window)

        if target is None:
            return

        repo_path = osp.join(work_on_params['project_root'],target.repo)
        path = osp.join(work_on_params['project_root'],target.path)
        if not osp.exists(osp.dirname(repo_path)):
            os.makedirs(osp.dirname(repo_path),exist_ok=True)

        if not osp.exists(repo_path) and not target.wiki:
            if self.view.settings().get('puppet_scm_auto_clone_wikis'):
                wiki = self.async_cmd(parse_target('#'+target.ref), open_target=False, **args)
        repo = work_on(target.repo,target.branch,**work_on_params)

        window = self.window
        if target.focus:
            # TBD. Open an application folder in a new window
            pass
        elif target.path != target.repo and open_target:
            view = window.open_file(path, sublime.TRANSIENT)
            if not target.wiki and not target.suffix and osp.exists(path):
                if view.is_loading():
                    view.settings().set('sddc_yaml_loc', target.subpath)
                else:
                    goto_yaml_key(view, target.subpath)
        return repo


class PuppetWorkOnEventListener(EventListener):

    def on_load_async(self, view):
        subpath = view.settings().get('sddc_yaml_loc')
        if subpath is None:
            return
        view.settings().erase('sddc_yaml_loc')
        goto_yaml_key(view, subpath)


class PuppetWorkOnAppCommand(ProjectCommandHelper,AsyncMacroRunner,WindowCommand):
    def run(self, app_prefix=None, state=None):
        self.window.run_command('puppet_core_work_on',args={
            'target': app_prefix,
            'title': 'App Prefix',
            'default_text': '',
            'state': state
        })


other_mod_select = [['-','Other Application Module'],['^','Other Tenant Module'],['*','Other Global Module']]

class PuppetWorkOnModuleCommand(ProjectCommandHelper,AsyncMacroRunner,WindowCommand):
    def run(self, module_name=None, state=None):
        if module_name:
            self.on_select(module_name,state=state)
        elif module_name is None:
            work_on_params = get_work_on_params(self.window)
            modules = get_modules(work_on_params['project_root'])
            items = [[m.name,['Remote','Local'][m.is_local]] for m in modules]+other_mod_select
            self.window.show_quick_panel(items, partial(self.on_select,state=state), sublime.KEEP_OPEN_ON_FOCUS_LOST)

    def on_select(self, idx, state=None):
        work_on_params = get_work_on_params(self.window)
        modules = get_modules(work_on_params['project_root'])
        if idx>=len(modules):
            ms_idx = idx - len(modules)
            ms = other_mod_select[ms_idx]
            self.window.run_command('puppet_core_work_on',args={
                'title': 'Get {0}'.format(ms[ms_idx][1]),
                'default_text': ms[ms_idx][0] if ms_idx else '',
                'state': state
            })
        elif idx >= 0:
            mod = modules[idx]
            print(mod)
            if mod.scope=='globals':
                prefix = '*'
            elif mod.scope=='tenants':
                prefix = '^'
            else:
                prefix = ''
            self.window.run_command('puppet_core_work_on',args={
                'target': prefix+mod.name,
                'state': state
            })


class PuppetWorkOnNewBranchCommand(ContextCommandHelper,scm.RepoHelper,TextCommand):
    def run(self, edit, branch=None):
        repo = self.repo
        if not repo:
            return

        repo_path = repo.working_dir

        parent_dir = osp.dirname(repo_path)

        if osp.basename(parent_dir)!='modules' or osp.basename(osp.dirname(parent_dir))=='wiki':
            return

        branches = get_module_branches(repo)

        work_on_params = self.work_on_params

        if branch is not None:
            if branch in branches:
                work_on(repo_path,branch,**work_on_params)
        else:
            def on_select(idx):
                if 0 <= idx:
                    work_on(repo_path,branches[idx],**work_on_params)
            subtext = 'from: '+repo.head.ref.name
            items = [[b,subtext] for b in branches]
            self.window.show_quick_panel(items, on_select, sublime.MONOSPACE_FONT)
