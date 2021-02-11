"""Main plugin"""


import sublime  # pylint: disable=import-error
import sublime_plugin  # pylint: disable=import-error
import threading
import logging
import os
from .sublimetext import client
from .sublimetext import document, settings
from .sublimetext import ServerOffline, ServerError

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
sh = logging.StreamHandler()
sh.setFormatter(logging.Formatter("%(levelname)s\t%(module)s: %(lineno)d\t%(message)s"))
sh.setLevel(logging.DEBUG)
logger.addHandler(sh)


class StateManager:
    """Server state manager"""

    def __init__(self) -> None:
        self.online = False
        self.error = False
        self.workspace_directory = None

    def __repr__(self) -> str:
        return (
            "error: {error}, online: {online}, "
            "workspace_directory: {workspace_directory}"
            "".format(
                error=self.error,
                online=self.online,
                workspace_directory=self.workspace_directory,
            )
        )

    def reset(self) -> None:
        self.online = False
        self.error = False
        self.initialized = False
        self.workspace_directory = None


class Settings:
    """SublimeText Settings handler"""

    def __init__(self):
        self.autocomplete = True
        self.documentation = True
        self.format_document = True
        self.settings = sublime.load_settings(
            "Pytools.sublime-settings"
        )  # type : sublime.Settings

    def initialize(self) -> None:
        """initialize"""

        self.autocomplete = self.settings.get("autocomplete", True)
        self.documentation = self.settings.get("documentation", True)
        self.format_document = self.settings.get("format_document", True)
        self.settings.add_on_change("autocomplete", self.on_complete_change)
        self.settings.add_on_change("documentation", self.on_documentation_change)
        self.settings.add_on_change("format_document", self.on_format_document_change)

    def on_complete_change(self) -> None:
        self.autocomplete = self.settings.get("autocomplete", True)

    def on_documentation_change(self) -> None:
        self.documentation = self.settings.get("documentation", True)

    def on_format_document_change(self) -> None:
        self.format_document = self.settings.get("format_document", True)


SERVER_STATE = StateManager()
SETTINGS = Settings()


def ignore(config: bool):
    """cancel if ignored"""

    def execute(func):
        def wrapper(*args, **kwargs):
            if not config:
                logger.debug("function ignored")
                return None
            return func(*args, **kwargs)

        return wrapper

    return execute


def online() -> bool:
    logger.debug("online: %s", SERVER_STATE.online)
    return SERVER_STATE.online


def can_run_server(func):
    """run server if not running, bypass if already running"""

    def wrapper(*args, **kwargs):
        if SERVER_STATE.online:
            return func(*args, **kwargs)
        logger.debug("required running server")
        window = sublime.active_window()
        window.run_command("pytools_runserver")
        return None

    return wrapper


def server_valid(func):
    """cancel if server error"""

    def wrapper(*args, **kwargs):
        if SERVER_STATE.error:
            logger.debug("server error")
            return None
        logger.debug("server valid")
        return func(*args, **kwargs)

    return wrapper


REQUEST_LOCK = threading.RLock()


def request_queue(func):
    """only single request, pending other"""

    def wrapper(*args, **kwargs):
        with REQUEST_LOCK:
            logger.debug("requesting")
            return func(*args, **kwargs)

    return wrapper


PROCESS_LOCK = threading.Lock()


def process_lock(func):
    """only run single process. cancel if any running"""

    def wrapper(*args, **kwargs):
        if PROCESS_LOCK.locked():
            logger.debug("process locked")
            return None
        with PROCESS_LOCK:
            logger.debug("processing")
            return func(*args, **kwargs)

    return wrapper


@request_queue
def check_connection():
    """check any server connected"""
    try:
        logger.debug("check connection")
        results = client.ping()
        logger.debug(results)
    except ServerOffline:
        logger.debug("connection error")
        SERVER_STATE.online = False
    else:
        SERVER_STATE.online = True


def plugin_loaded():
    """on plugin loaded"""

    SERVER_STATE.reset()
    SETTINGS.initialize()
    thread = threading.Thread(target=check_connection)
    thread.start()


def valid_source(view, pos=0):
    """python source file"""

    return view.match_selector(pos, "source.python")


def validate_source(func):
    """validate source at active view"""

    def wrapper(*args, **kwargs):
        view = sublime.active_window().active_view()
        return func(*args, **kwargs) if validate_source(view) else None

    return wrapper


def valid_attribute(view, pos):
    """attribute in valid scope"""

    result = view.match_selector(pos, "source.python")
    result = not view.match_selector(pos, "comment") and result
    result = not view.match_selector(pos, "string") and result
    return result


@request_queue
def change_workspace(path_directory):
    """change workspace

    Raises:
        ServerOffline"""

    if SERVER_STATE.workspace_directory == path_directory:
        return
    results = client.change_workspace(path_directory)
    SERVER_STATE.workspace_directory = results.results["workspace_directory"]
    return


# FIXME: SHOW ERROR MESSAGE IN STATUS BAR
# sublime.Window().status_message("message")

# FIXME: RUN SERVER ON INIT HOVER AND COMPLETION


class PyTools(sublime_plugin.EventListener):
    """Event based command"""

    def __init__(self):
        self.completion = None
        self.old_prefix = ""

    @can_run_server
    @server_valid
    @process_lock
    @request_queue
    def fetch_completion(self, view, prefix, location):
        """fetch completion thread"""

        self.old_prefix = prefix

        start = 0
        end = location
        word_region = view.word(location)
        if view.substr(word_region).isidentifier() and len(prefix) > 1:
            end = word_region.a  # complete at first identifier offset
        source_region = sublime.Region(start, end)
        line, character = view.rowcol(end)  # get rowcol at end selection

        def make_completion(completions):
            for completion in completions:
                yield (
                    "%s\t%s" % (completion["label"], completion["type"]),
                    completion["label"],
                )

        try:
            change_workspace(os.path.dirname(view.file_name()))
            result = client.fetch_completion(
                view.substr(source_region), line, character
            )
        except ServerOffline:
            return
        else:
            self.completion = (
                [] if not result else list(make_completion(result.results))
            )
            document.show_completions(view)

    @ignore(SETTINGS.autocomplete)
    @validate_source
    def on_query_completions(self, view, prefix, locations):
        """on query completion listener"""

        if not valid_attribute(view, locations[0]):
            return None

        def completon_build(completion):
            if not completion:
                return None
            return (
                completion,
                sublime.INHIBIT_WORD_COMPLETIONS | sublime.INHIBIT_EXPLICIT_COMPLETIONS,
            )

        if isinstance(self.completion, list):
            completion = self.completion if prefix.startswith(self.old_prefix) else None
            self.completion = None
            return completon_build(completion)

        thread = threading.Thread(
            target=self.fetch_completion, args=(view, prefix, locations[0])
        )
        thread.start()
        return None

    @can_run_server
    @process_lock
    @server_valid
    @request_queue
    def fetch_documentation(self, view, location):
        """fetch documentation thread"""

        start = 0
        word_region = view.word(location)
        if view.substr(word_region).isidentifier():
            end = word_region.b  # select until end of word
        else:
            return  # cancel request for non identifier
        source_region = sublime.Region(start, end)
        line, character = view.rowcol(end)  # get rowcol at end selection

        def decorate(content):
            return '<div style="padding: .5em">%s</div>' % content

        def goto(view, link):
            if not link:
                return None

            view_path = os.path.abspath(view.file_name())
            path = "{mod_path}:{line}:{character}".format(
                mod_path=view_path if link["path"] is None else link["path"],
                line=0 if link["line"] is None else link["line"],
                character=0 if link["character"] is None else link["character"] + 1,
            )
            return document.open(view, path)

        try:
            change_workspace(os.path.dirname(view.file_name()))
            result = client.fetch_documentation(
                view.substr(source_region), line, character
            )
        except ServerOffline:
            pass
        else:
            if not result.results:
                return  # cancel
            content = result.results.get("html")
            link = result.results.get("link")

            document.show_popup(
                view, decorate(content), location, lambda _: goto(view, link)
            )

    @ignore(SETTINGS.documentation)
    @validate_source
    def on_hover(self, view, point, hover_zone):
        """on hover listener"""

        if hover_zone == sublime.HOVER_TEXT:
            logger.debug("on hover")

            if not valid_attribute(view, point):
                return
            thread = threading.Thread(
                target=self.fetch_documentation, args=(view, point)
            )
            thread.start()


class PytoolsFormatCommand(sublime_plugin.TextCommand):
    """Formatting command"""

    def run(self, edit):
        view = self.view
        if not valid_source(view):
            return

        self.format_document(view, edit)

    @ignore(SETTINGS.format_document)
    @validate_source
    @server_valid
    def format_document(self, view, edit):
        src = view.substr(sublime.Region(0, view.size()))
        try:
            result = client.format_code(src)
        except ServerOffline:
            pass
        else:
            logger.debug(result)
            document.apply_changes(view, edit, result.results)

    def is_visible(self):
        return valid_source(self.view)


class PytoolsChangeWorkspaceCommand(sublime_plugin.TextCommand):
    """Change workspace command"""

    @server_valid
    def run(self, edit, path=None):
        view = self.view
        if not valid_source(view):
            return
        file_name = view.file_name()
        if not file_name:
            return
        path = os.path.dirname(file_name)
        logger.debug("init change_workspace")

        def change_thread(path):
            try:
                change_workspace(path)
            except ServerOffline:
                pass

        thread = threading.Thread(target=change_thread, args=(path,))
        thread.start()


class PytoolsShutdownserverCommand(sublime_plugin.WindowCommand):
    """Shutdown command"""

    def run(self):
        logger.debug("init shutdown server")
        thread = threading.Thread(target=self.exit)
        thread.start()

    @request_queue
    def exit(self):
        if SERVER_STATE.error:  # cancel all request if server error
            return
        try:
            response = client.shutdown()
        except ServerOffline:
            pass
        else:
            SERVER_STATE.reset()
            logger.debug("finish shutdown server")


class PytoolsRunserverCommand(sublime_plugin.WindowCommand):
    """Run server command"""

    def run(self):
        subl_settings = sublime.load_settings("Pytools.sublime-settings")
        python_path = subl_settings.get("path")
        thread = threading.Thread(target=self.run_server, args=(python_path,))
        thread.start()

    @process_lock
    def run_server(self, python_path):
        if SERVER_STATE.error:  # cancel all request if server error
            return
        activate_path = settings.find_activate(python_path)
        env_path = settings.find_environment(python_path)
        activate = [path for path in (activate_path, env_path) if path]
        try:
            logger.debug("running server")
            client.run_server(activate)
            SERVER_STATE.online = True
        except ServerError:
            logger.debug("server error")
            SERVER_STATE.error = True
            SERVER_STATE.online = False
        else:
            logger.debug("server ready")
            self.window.status_message("Server ready")
            self.window.active_view().run_command("pytools_change_workspace")


class PytoolsPythonInterpreterCommand(sublime_plugin.WindowCommand):
    """Load python interpreter command"""

    def run(self):
        window = self.window
        settings.set_interpreter(window)


class PytoolsStateinfoCommand(sublime_plugin.WindowCommand):
    """Load python interpreter command"""

    def run(self):
        print(SERVER_STATE)


class PytoolsTestCommand(sublime_plugin.WindowCommand):
    """Load python interpreter command"""

    def run(self):
        print(SERVER_STATE)
        message = "Server required to perform autocomplete, documentation and formatting.\n\nRun server?"
        result = sublime.yes_no_cancel_dialog(
            msg=message, yes_title="Run", no_title="Ignore"
        )
        print(result)
