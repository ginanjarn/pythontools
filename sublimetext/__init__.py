"""SublimeText"""

import threading
import sublime
import os
from .client import Service
from . import document
import logging

logger = logging.getLogger("sublime __init__")
logger.setLevel(logging.DEBUG)


process_lock = threading.Lock()

def runnable(func):
    def wrapper(*args, **kwargs):
        if process_lock.locked():
            return
        with process_lock:
            return func(*args, **kwargs)
    return wrapper

class ClientHelper:
    """Client helper class"""

    def __init__(self):
        self.service = Service()
        self.completion = None
        self.completion_prefix = ""

    @runnable
    def exit(self):
        if self.service.server_error:   # cancel all request if server error
            return
        self.service.exit()

    @runnable
    def fetch_completion(self, view,prefix, location):
        self.completion_prefix = prefix
        if self.service.server_error:   # cancel all request if server error
            return
        # fetch completion
        start = 0
        end = location
        word_region = view.word(location)           
        if view.substr(word_region).isidentifier():
            end = word_region.a  # complete at first identifier offset
        source_region = sublime.Region(start, end)
        line, character = view.rowcol(end)  # get rowcol at end selection
        result = self.service.complete(view.substr(source_region), line, character)
        logger.debug(result)

        def make_completion(completions):
            for completion in completions:
                logger.debug(completion)
                yield (
                    "%s\t%s" % (completion["label"], completion["type"]),
                    completion["label"],
                )

        self.completion = None if not result else list(make_completion(result))
        # then request to show
        document.show_completions(view)
        pass        

    @runnable
    def fetch_documentation(self, view, location):
        if self.service.server_error:   # cancel all request if server error
            return
        # fetch documentation
        start = 0
        word_region = view.word(location)
        if view.substr(word_region).isidentifier():
            end = word_region.b  # select until end of word
        else:
            return  # cancel request for non identifier
        source_region = sublime.Region(start, end)
        line, character = view.rowcol(end)  # get rowcol at end selection
        # service.hover()
        result = self.service.hover(view.substr(source_region), line, character)

        def get_content(documentation):
            return documentation.get("html") if documentation else None        

        content = get_content(result)
        def decorate(content):
            return "<div style=\"padding: .25em\">%s</div>"%content
        # print(content)
        # then request to show
        if content:
            content = decorate(content)
            goto = lambda path: document.open(view, path)
            document.show_popup(view, content, location, goto)
        pass

    @runnable
    def format_code(self, view, edit):
        if self.service.server_error:   # cancel all request if server error
            return
        # fetch formatted
        start = 0
        end = view.size()
        source_region = sublime.Region(start, end)
        src = view.substr(source_region)
        # service.document_format()
        result = self.service.document_format(src)
        # then request to show
        document.apply_changes(view, edit, result)
        # self.formatted_changes = result
        # view.run_command("pytools_format")
        pass

    @runnable
    def change_workspace(self, view, path=None):
        try:
            path = os.path.dirname(view.file_name()) if path is None else path
        except TypeError:
            pass
        else:
            self.service.change_workspace(path)
