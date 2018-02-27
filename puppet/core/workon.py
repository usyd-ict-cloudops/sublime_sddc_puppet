
import os
import os.path as osp
import sublime
from sublime_plugin import WindowCommand
from sddc_common.async import AsyncMacroRunner
from sddc_common.workflow import work_on
from .utils import ProjectCommandHelper, parse_target, get_work_on_params, find_yaml_key
from functools import partial


class PuppetCoreWorkOnCommand(ProjectCommandHelper,AsyncMacroRunner,WindowCommand):

	def run(self, path=None, title='Work On', default_text='', state=None):
		if path:
			self.on_target(path,state=state)
		elif path is None:
			self.window.show_input_panel(title, default_text, partial(self.on_target,state=state))

	def on_target(self, target, state=None):
		'''path, branch=None, acct=None, project_root=None, rewrite_map=None, provider=None, url_fmt=None, off_branch=None'''
		if osp.exists(target):
			if not osp.isdir(target):
				self.window.open_file(target)
			return

		if parse_target(target) is None:
			return

		self.run_command(state=state,target=target)

	def async_cmd(self, target):
		'''
		Get a repo and open the needed file based on a target ref

		ref: #?[*^]?<prefix>(|<aertype>|~<quick>|_<name>)(|@<branch>)(|/|:<subpath>)

		'''
		work_on_params = get_work_on_params(self.window)
		target = parse_target(target)
		if target is None:
			return

		repo_path = osp.join(work_on_params['project_root'],target.repo)
		path = osp.join(work_on_params['project_root'],target.path)
		if not osp.exists(osp.dirname(repo_path)):
			os.makedirs(osp.dirname(repo_path),exist_ok=True)
		try:
			repo = work_on(target.repo,target.branch,**work_on_params)
		except:
			return

		window = self.window
		if target.focus:
			# TBD. Open an application folder in a new window
			pass
		if target.path != target.repo:
			flags = sublime.TRANSIENT
			if not target.wiki and not target.suffix and osp.exists(path):
				row = find_yaml_key(path, target.subpath)
				if row is not None:
					path = '{0}:{1}'.format(path,row)
					flags |= sublime.ENCODED_POSITION
			return window.open_file(path, flags)
		return repo
