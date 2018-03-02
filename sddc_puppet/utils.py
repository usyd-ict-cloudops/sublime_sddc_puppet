import sublime
import re
import os.path as osp
from collections import namedtuple

SETTINGS_FILE = 'SDDC.sublime-settings'

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
        'module': 'applications/{prefix}/modules/{prefix}_{name}',
        'module_wiki': 'applications/{prefix}/wiki/modules/{prefix}_{name}'
    },
    'tenants': {
        'data': 'tenants/{prefix}/data',
        'data_wiki': 'tenants/{prefix}/wiki/data',
        'module': 'tenants/{prefix}/modules/{prefix}_{name}',
        'module_wiki': 'tenants/{prefix}/wiki/modules/{prefix}_{name}'
    },
    'globals': {
        'data': 'global/data/{prefix}',
        'data_wiki': 'global/wiki/data/{prefix}',
        'module': 'global/modules/{prefix}_{name}',
        'module_wiki': 'global/wiki/modules/{prefix}_{name}'
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
    'tenants': '(?<=\\^)[a-z][a-z0-9]{3}',
    'applications': '(?<![*^])(?:[a-z][a-z0-9]{3}|)[a-z][a-z0-9]{3}',
    'suffix': '_(?P<suffix>[a-z][a-z0-9_]{1,24})',
    'quick': '\\~(?P<quick>[dmo]|l[dpst]|[do][fko]\w(?P<release>\w*))',
    'data': '(?P<app>\\.{0,2})|(?P<type>[a-z0-9]{2})|(?P<env>[a-z0-9])\\.?|\\.(?P<role>[a-z0-9.])',
    'branch': '(?:|@(?P<branch>\w+))',
    'subpath': '(?:|(?P<focus>/)|:(?P<subpath>.*))'
}

target_regex_frame = '^{wiki}{scope}(?P<prefix>{globals}|{tenants}|{applications})(?:{data}|{quick}|{suffix}){branch}{subpath}$'

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


class ProjectCommandHelper(object):

    def is_enabled(self,*args,**kwargs):
        return self.window.settings().get('is_puppet',False)

    def is_visible(self,*args,**kwargs):
        return self.is_enabled(*args,**kwargs)


# settings helpers

def get_settings():
    return sublime.load_settings(SETTINGS_FILE)


def get_setting(key, default=None):
    return get_settings().get(key, default)


def get_git_executable(default='git'):
    return get_setting('git_executable', default)


def get_repo_path_format(scope,repo_type):
    return get_setting('puppet_repo_path_format',repo_path_format)[scope][repo_type]


def get_work_on_params(obj):
    '''Pass a View or Window object to get the params required for sddc_common.workflow.work_on'''
    window,view = obj.window(),obj if isinstance(obj, sublime.View) else obj,obj.active_view()
    return {
        'project_root': window.extract_variables().get('folder'),
        'acct': view.settings().get('team'),
        'rewrite_map': view.settings().get('url_map'),
        'provider': view.settings().get('git_repo_provider_authority'),
        'url_fmt': view.settings().get('repo_url_format_string')
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
            elif ext=='pp' and not t['subpath'].startswith('manifests/'):
                fn_fmt = 'manifests/{subpath}'
            elif ext=='erb' and not t['subpath'].startswith('templates/'):
                fn_fmt = 'templates/{subpath}'
            elif ext=='rb' and not t['subpath'].startswith('lib/'):
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
    return osp.normpath(osp.join(t['repo'],fn_fmt.format(**t)))


def parse_target(target):
    '''Convert target ref to Target namedtuple'''
    match = target_regex.match(target)
    if not match:
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


def find_yaml_key(path,key):
    """TBD."""
    return
