"""
Example OpenServerless Plugin — Chapter 4
Demonstrates the standard plugin registration pattern.
Every plugin exposes register_plugin() which is discovered
by the ops CLI at startup.
"""

__version__ = '1.0.0'
__plugin_name__ = 'example'


def register_plugin():
    from . import operator
    return {
        'name': __plugin_name__,
        'version': __version__,
        'description': 'Example plugin for Chapter 4 — Mastering Apache OpenServerless',
        'operator_module': operator,
        'cli_tasks': 'opsfile.yml',
        'crd_file': 'crd.yaml',
        'dependencies': [],
    }
