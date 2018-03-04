import os
import os.path as osp
import sublime
from sublime_plugin import WindowCommand
from sddc_common.async import AsyncMacroRunner
from sddc_common.workflow import work_on
from .utils import ProjectCommandHelper, parse_target, get_work_on_params, find_yaml_key, noop, get_modules
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

    def async_cmd(self, target, **args):
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
            wiki = self.async_cmd('#'+target.ref, **args)
        repo = work_on(target.repo,target.branch,**work_on_params)

        window = self.window
        if target.focus:
            # TBD. Open an application folder in a new window
            pass
        elif target.path != target.repo:
            view = window.open_file(path, sublime.TRANSIENT)
            if not target.wiki and not target.suffix and osp.exists(path):
                symbol = find_yaml_key(path, target.subpath)
                if symbol is not None:
                    view.show_at_center(symbol.region)
                    view.sel().clear()
                    view.sel().add(sublime.Region(symbol.region.end() + 1))
        return repo


class PuppetGetAppCommand(ProjectCommandHelper,AsyncMacroRunner,WindowCommand):
    def run(self, app_prefix=None, state=None):
            self.window.run_command('puppet_core_work_on',args={
                'target': app_prefix,
                'title': 'Get App',
                'default_text': 'default_text',
                'state': state
            })


other_mod_select = [['-','Other Application Module'],['^','Other Tenant Module'],['*','Other Global Module']]

class PuppetGetModuleCommand(ProjectCommandHelper,AsyncMacroRunner,WindowCommand):
    def run(self, module_name=None, state=None):
        if module_name:
            self.on_target(module_name,state=state)
        elif module_name is None:
            work_on_params = get_work_on_params(self.window)
            modules = get_modules(work_on_params['project_root'])
            items = [[m.name,['Remote','Local'][m.is_local]] for m in modules]+other_mod_select
            self.window.show_quick_panel(items, partial(self.on_state,state=state), sublime.KEEP_OPEN_ON_FOCUS_LOST)

    def on_select(self, idx, state=state):
            work_on_params = get_work_on_params(self.window)
            modules = get_modules(work_on_params['project_root'])
            if idx>=len(modules):
                ms_idx = idx - len(modules)
                ms = other_mod_select[other_idx]
                self.window.run_command('puppet_core_work_on',args={
                    'title': 'Get {0}'.format(ms[ms_idx][1]),
                    'default_text': ms[ms_idx][0] if ms_idx else '',
                    'state': state
                })
            elif idx >= 0:
                mod = modules[idx]
                if mod.scope=='global':
                    prefix = '*'
                elif mod.scope=='tenant':
                    prefix = '^'
                else:
                    prefix = ''
                self.window.run_command('puppet_core_work_on',args={
                    'target': prefix+mod.name,
                    'state': state
                })
