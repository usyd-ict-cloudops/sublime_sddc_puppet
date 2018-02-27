
import sublime
import sublime_plugin


def plugin_loaded():
	from .puppet.core import workon
