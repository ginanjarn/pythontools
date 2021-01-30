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
    result = not view.match_selector(pos,"string") and result
    return result

class PyTools(sublime_plugin.EventListener, ClientHelper):
    """Event based command"""

    def on_query_completions(self, view, prefix, locations):
        location = locations[0]
        if not valid_attribute(view, location):
            return None
        
        def completon_build(completion):
            if not completion:
                return
            return (
                completion, sublime.INHIBIT_WORD_COMPLETIONS | sublime.INHIBIT_EXPLICIT_COMPLETIONS
                )

        if self.completion:
            completion = self.completion if prefix.startswith(self.completion_prefix) else None
            self.completion = None
            return completon_build(completion)
        else:
            thread = threading.Thread(target=self.fetch_completion, args=(view, prefix, location))
            thread.start()
        

    def on_hover(self, view, point, hover_zone):
        if not valid_attribute(view, point):
            return
        
        if hover_zone == sublime.HOVER_TEXT:
            thread = threading.Thread(target=self.fetch_documentation, args=(view,point))
            thread.start()
        pass

    def on_activated(self, view):
        if not valid_source(view):
            return
            
        if self.service.server_online:
            logger.debug("server server_online")
            view.run_command("pytools_set_workspace")



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

class PytoolsSetWorkspaceCommand(sublime_plugin.TextCommand):
    """Formatting command"""
    def run(self, edit, path=None):
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
        helper.change_workspace(view, path)
        logger.debug("change change_workspace")
        pass

class PytoolsShutdownserverCommand(sublime_plugin.WindowCommand):
    """Shutdown command"""
    def run(self):
        helper = ClientHelper()
        thread = threading.Thread(target=helper.exit)
        thread.start()
