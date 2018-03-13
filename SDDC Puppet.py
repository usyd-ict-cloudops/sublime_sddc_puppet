from __future__ import absolute_import, unicode_literals, print_function, division

import sys

"""This module collates the commands from the submodule

...it's a python 2 / 3 compatibility workaround, mostly.
"""

# Sublime doesn't reload submodules. This code is based on 1_reloader.py
# in Package Control, and handles that.

mod_prefix = 'sddc_puppet'

# ST3 loads each package as a module, so it needs an extra prefix
if sys.version_info >= (3,):
    bare_mod_prefix = mod_prefix
    mod_prefix = 'SDDC Puppet.' + mod_prefix
    from imp import reload

# Modules have to be reloaded in dependency order. So list 'em here:
mods_load_order = [
    '',

    '.utils',
    '.workon',
    '.project',
    '.eyaml',
    '.deploy',
    '.sync'
]

reload_mods = [mod for mod in sys.modules if mod[0:11] in ('sddc_puppet', 'SDDC Puppet') and sys.modules[mod] is not None]

reloaded = []
for suffix in mods_load_order:
    mod = mod_prefix + suffix
    if mod in reload_mods:
        reload(sys.modules[mod])
        reloaded.append(mod)

if reloaded:
    print("SDDC Puppet: reloaded submodules", reloaded)

# Now actually import all the commands so they'll be visible to Sublime
from .sddc_puppet.workon import PuppetCoreWorkOnCommand, PuppetWorkOnAppCommand, PuppetWorkOnModuleCommand, PuppetWorkOnNewBranchCommand
from .sddc_puppet.project import PuppetCoreProjectCommand, PuppetProjectCommand
from .sddc_puppet.eyaml import EyamlEncryptCommand
from .sddc_puppet.deploy import PuppetCoreDeployCommand, PuppetDeployCommand, PuppetTemplateCommand, PuppetDeployEventListener
from .sddc_puppet.sync import PuppetCoreSyncCommand, PuppetSyncCommand
from sddc_common import *
