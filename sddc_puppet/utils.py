import sublime
import re
import os.path as osp
from collections import namedtuple
from glob import glob
import yaml
from sddc_common import scm

SETTINGS_FILE = 'SDDC Puppet.sublime-settings'

module_branch_order = [
    ['master'],
    ['production'],
    ['test'],
    ['development'],
    ['scratch'],
    [
        'scratch1','scratch2','scratch3',
        'scratch4','scratch5','scratch6',
        'scratch7','scratch8','scratch9'
    ]
]

module_branches = sum(module_branch_order,[])

repo_path_format = {
    'applications': {
        'data': 'applications/{prefix}/data',
        'data_wiki': 'applications/{prefix}/wiki/data',
        'module': 'applications/{prefix}/modules/{prefix}_{suffix}',
        'module_wiki': 'applications/{prefix}/wiki/modules/{prefix}_{suffix}'
    },
    'tenants': {
        'data': 'tenants/{prefix}/data',
        'data_wiki': 'tenants/{prefix}/wiki/data',
        'module': 'tenants/{prefix}/modules/{prefix}_{suffix}',
        'module_wiki': 'tenants/{prefix}/wiki/modules/{prefix}_{suffix}'
    },
    'globals': {
        'data': 'global/data/{prefix}',
        'data_wiki': 'global/wiki/data/{prefix}',
        'module': 'global/modules/{prefix}_{suffix}',
        'module_wiki': 'global/wiki/modules/{prefix}_{suffix}'
    }
}

quick_defaults = {
    'd':'defaults',
    'dkl': 'defaults_kernel_Linux',
    'dkw': 'defaults_kernel_windows',
    'dfr': 'defaults_osfamily_RedHat',
    'dfu': 'defaults_osfamily_Ubuntu',
    'dfw': 'defaults_osfamily_Windows',
    'dfa': 'defaults_osfamily_Amazon',
    'dfr': 'defaults_osfamily_RedHat',
    'dfu': 'defaults_osfamily_Ubuntu',
    'dfw': 'defaults_osfamily_Windows',
    'ld': 'lifecycle_development',
    'lp': 'lifecycle_production',
    'ls': 'lifecycle_scratch',
    'lt': 'lifecycle_test',
    'm':'metadata',
    'o': 'overrides',
    'okl': 'overrides_kernel_Linux',
    'okw': 'overrides_kernel_windows',
    'ofr': 'overrides_osfamily_RedHat',
    'ofu': 'overrides_osfamily_Ubuntu',
    'ofw': 'overrides_osfamily_Windows',
    'ofa': 'overrides_osfamily_Amazon',
    'ofr': 'overrides_osfamily_RedHat',
    'ofu': 'overrides_osfamily_Ubuntu',
    'ofw': 'overrides_osfamily_Windows'
}

target_regex_parts = {
    'wiki': '(?P<wiki>#|)',
    'scope':'(?P<scope>[*^]|)',
    'globals': '(?<=[*])[a-z][a-z0-9]{1,24}',
    'tenants': '(?<=\\^)org_[a-z][a-z0-9]{3}',
    'applications': '(?<![*^])(?:[a-z][a-z0-9]{3}|)[a-z][a-z0-9]{3}',
    'suffix': '_(?P<suffix>[a-z][a-z0-9_]{1,24})',
    'quick': '\\~(?P<quick>[dmo]|l[dpst]|[do][fko]\w(?P<release>\w*))',
    'data': '(?P<app>\\.{0,2})|(?P<type>[a-z0-9]{2})|(?P<env>[a-z0-9])\\.?|\\.(?P<role>[a-z0-9.])',
    'branch': '(?:|@(?P<branch>\w+))',
    'subpath': '(?:|(?P<focus>/)|:(?P<subpath>.*))'
}

target_regex_frame = '^{wiki}{scope}(?P<prefix>{applications}|{tenants}|{globals})(?:{data}|{quick}|{suffix}){branch}{subpath}$'

target_regex = re.compile(target_regex_frame.format(**target_regex_parts))

target_scopes = {'':'applications','*':'globals','^':'tenants'}

Target = namedtuple('Target', [
    'ref','path','repo','branch','subpath',
    'focus','wiki','scope','prefix','suffix',
    'quick','release','app','env','role','type'])


def noop(*args, **kwargs):
    pass


def get_promote_targets(branch,is_src=True):
    if branch in module_branches:
        idx = [i for i,sibs in enumerate(module_branch_order) if branch in sibs][0]
        if is_src:
            s,e = None,idx+1
        else:
            s,e = idx,None
        return [b for b in sum(module_branch_order[s:e],[]) if b != branch]


def get_module_branches(repo):
    names = scm.branch_names(repo)
    return [branch for branch in module_branches if branch not in names]


def expand_path(path,window=None):
    window = sublime.active_window() if window is None else window
    return sublime.expand_variables(osp.expanduser(path),window.extract_variables())

def is_puppet(view):
    return view.settings().get('is_puppet',False)


class PuppetCommandHelper(object):

    def is_puppet(self):
        return is_puppet(self.view)

    def get_setting(self, setting, default=None):
        return self.view.settings().get(setting,get_setting(setting,default))

    def get_file_setting(self, setting, default=None):
        return expand_path(self.get_setting(setting,default), self.window)


class NotProjectCommandHelper(PuppetCommandHelper):

    @property
    def view(self):
        return self.window.active_view()


class PuppetOnlyCommandHelper(PuppetCommandHelper):

    def is_enabled(self,*args,**kwargs):
        return self.is_puppet()

    @property
    def project_root(self):
        return self.window.extract_variables().get('folder')

    def find_view(self, **kwargs):
        for view in self.window.views():
            s = view.settings()
            if all(s.get(k) == v for k, v in list(kwargs.items())):
                return view

    @property
    def work_on_params(self):
        return {
            'project_root': self.project_root,
            'account': self.get_setting('puppet_scm_provider_account'),
            'rewrite_map': self.get_setting('puppet_scm_provider_url_map'),
            'provider': self.get_setting('puppet_scm_provider_authority'),
            'url_fmt': self.get_setting('puppet_scm_repo_url_format_string')
        }


class ProjectCommandHelper(PuppetOnlyCommandHelper):

    @property
    def view(self):
        return self.window.active_view()


class ContextCommandHelper(PuppetOnlyCommandHelper):

    @property
    def window(self):
        return self.view.window()

    @property
    def app_prefix(self):
        fn = self.view.file_name()
        if fn and fn.startswith(osp.join(self.project_root,'applications')):
            return osp.relpath(fn,osp.join(self.project_root,'applications')).split(osp.sep)[0]
        return None


class YAMLHelper(ContextCommandHelper):

    def is_enabled(self,*args,**kwargs):
        return bool(self.is_puppet() and self.view.file_name() and osp.splitext(self.view.file_name())[-1]=='.yaml')

# settings helpers

def get_settings():
    return sublime.load_settings(SETTINGS_FILE)


def get_setting(key, default=None):
    return get_settings().get(key, default)


def get_git_executable(default='git'):
    return get_setting('git_executable', default)


def get_repo_path_format(scope,repo_type):
    return get_setting('puppet_repo_path_format',repo_path_format)[scope][repo_type]


def get_work_on_params(window):
    '''Pass a View or Window object to get the params required for sddc_common.workflow.work_on'''
    settings = window.active_view().settings()
    return {
        'project_root': window.extract_variables().get('folder'),
        'account': settings.get('puppet_scm_provider_account'),
        'rewrite_map': settings.get('puppet_scm_provider_url_map'),
        'provider': settings.get('puppet_scm_provider_authority'),
        'url_fmt': settings.get('puppet_scm_repo_url_format_string')
    }


def convert_quick(q):
    return get_setting('puppet_target_quick_map',quick_defaults).get(q[:3])


def calculate_target_path(t):
    fn_fmt = ''
    if t['wiki']:
        fn_fmt = '{subpath}' if t['subpath'] else 'Home.md'
    if t['suffix']:
        if t['subpath'] is not None:
            ext = osp.splitext(t['subpath'])[-1]
            fn_fmt = '{subpath}'
            if t['subpath']=='':
                fn_fmt = 'README.md'
            elif ext=='.pp' and not t['subpath'].startswith('manifests/'):
                fn_fmt = 'manifests/{subpath}'
            elif ext=='.erb' and not t['subpath'].startswith('templates/'):
                fn_fmt = 'templates/{subpath}'
            elif ext=='.rb' and not t['subpath'].startswith('lib/'):
                fn_fmt = 'lib/{subpath}' if osp.sep in t['subpath'] else 'lib/facter/{subpath}'
    elif t['scope']!='applications':
        if t['quick']:
            if t['release']:
                fn_fmt = '{0}_{1}.yaml'.format(convert_quick(t['quick']),t['release'])
            else:
                fn_fmt = '{0}.yaml'.format(convert_quick(t['quick']))
        elif t['subpath']:
            fn_fmt = '{subpath}'
        else:
            fn_fmt = 'README.md'
    elif t['type']:
        fn_fmt = 'type_{type}.yaml'
    elif t['env']:
        fn_fmt = 'env_{env}.yaml'
    elif t['role']:
        fn_fmt = 'role_{role}.yaml'
    elif t['quick'] and t['quick'][:1] in 'ml':
        fn_fmt = '{0}.yaml'.format(convert_quick(t['quick']))
    elif t['app']:
        fn_fmt = '{subpath}' if t['subpath'] else 'README.md'
    else:
        fn_fmt = 'app.yaml'
    print(fn_fmt)
    return osp.normpath(osp.join(t['repo'],fn_fmt.format(**t)))


def parse_target(target):
    '''Convert target ref to Target namedtuple'''
    match = target_regex.match(target)
    if not match:
        print('Invalid Target: {0!r}'.format(target))
        return

    t = match.groupdict()
    t['wiki'] = bool(t['wiki'])
    t['focus'] = bool(t['focus'])
    t['scope'] = target_scopes[t['scope']]

    if t['scope']!='applications':
        if t['app'] or t['env'] or t['role'] or t['type']:
            return

    if t['branch'] is not None and t['branch'] not in module_branches:
        return

    if not t['suffix'] or t['wiki']:
        if t['branch'] not in (None,'master'):
            return

    repo_type = ['{0}','{0}_wiki'][t['wiki']].format('module' if t['suffix'] else 'data')
    t['repo'] = get_repo_path_format(t['scope'],repo_type).format(**t)

    return Target(target, calculate_target_path(t), **t)


YAMLSymbol = namedtuple('YAMLSymbol', ['name','region'])


def get_yaml_symbols(view):
    """Get yaml key symbols"""

    regions = view.find_by_selector('entity.name.tag.yaml')
    content = view.substr(sublime.Region(0, view.size()))

    symbols = []
    current_path = []

    for region in regions:
        key = content[region.begin():region.end()]

        # Characters count from line beginning to key start position
        indent_level = region.begin() - content.rfind("\n", 0, region.begin()) - 1

        # Pop items from current_path while its indentation level less than current key indentation
        while len(current_path) > 0 and current_path[-1]["indent"] >= indent_level:
            current_path.pop()

        current_path.append({"key": key, "indent": indent_level})

        symbol_name = ".".join(map(lambda item: item["key"], current_path))
        symbols.append(YAMLSymbol(name=symbol_name, region=region))

    return symbols


def find_yaml_key(view, key):
    """Find the region within a view that matches key."""
    for symbol in get_yaml_symbols(view):
        if symbol.name==key:
            return symbol


PuppetModule = namedtuple('PuppetModule', ['is_local','scope','name','in_metadata'])


def get_modules(project_root):
    '''Return a list of PuppetModules'''

    mods = {}
    lf_mods = {}
    md_mods = {}
    for scope in target_scopes.values():
        lf_glob_target = osp.join(project_root,get_repo_path_format(scope,'module').format(prefix='*',suffix='*/'))
        lf_mods[scope] = set(osp.basename(osp.normpath(d)) for d in glob(lf_glob_target))
        md_mods[scope] = set()
        md_glob_target = osp.join(project_root,get_repo_path_format(scope,'data').format(prefix='*'),'metadata.yaml')
        for md_fn in glob(md_glob_target):
            with open(md_fn) as fp:
                md_mods[scope].update(yaml.safe_load(fp).get('modules',[]))
        mods[scope] = [PuppetModule(m in lf_mods[scope],scope,m,m in md_mods[scope]) for m in lf_mods[scope]|md_mods[scope]]

    return sorted(sum(mods.values(),[]))

def get_module(project_root, module_name):
    pass
