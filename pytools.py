"""Main plugin"""

import sublime  # pylint: disable=import-error
import sublime_plugin  # pylint: disable=import-error
import threading
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

from .sublimetext import ClientHelper


PLUGIN_READY = False

def plugin_loaded():
    global PLUGIN_READY
    PLUGIN_READY = True

def valid_source(view, pos=0):
    return view.match_selector(pos,"source.python")

def valid_attribute(view, pos):
    result = view.match_selector(pos,"source.python")
    result = not view.match_selector(pos,"comment") and result
    return result

class PyTools(sublime_plugin.EventListener, ClientHelper):
    """Event based command"""

    def on_query_completions(self, view, prefix, locations):
        location = locations[0]
        if not valid_attribute(view, location):
            return
        if self.completion:
            completion = self.completion
            self.completion = None
            return completion
        else:
            thread = threading.Thread(target=self.fetch_completion, args=(view, location))
            thread.start()
        pass

    def on_hover(self, view, point, hover_zone):
        if not valid_attribute(view, point):
            return
        
        if hover_zone == sublime.HOVER_TEXT:
            thread = threading.Thread(target=self.fetch_documentation, args=(view,point))
            thread.start()
        pass


class PytoolsFormatCommand(sublime_plugin.TextCommand):
    """Formatting command"""
    def run(self, edit):
        view = self.view
        if not valid_source(view):
            return
        
        # if any(self.formatted_changes):
        #     document.apply_changes(view, edit, self.formatted_changes)
        #     self.formatted_changes = ""
        #     return

        helper = ClientHelper()
        # thread = threading.Thread(target=helper.format_code, args=(view, edit))
        # thread = threading.Thread(target=self.format_code, args=(view, edit))
        # thread.start()
        helper.format_code(view, edit)
        pass

class PytoolsShutdownserverCommand(sublime_plugin.WindowCommand):
    """Shutdown command"""
    def run(self):
        helper = ClientHelper()
        thread = threading.Thread(target=helper.exit)
        thread.start()