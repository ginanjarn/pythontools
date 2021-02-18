"""Main plugin"""


import sublime  # pylint: disable=import-error
import sublime_plugin  # pylint: disable=import-error
import threading
import logging
import os
from .sublimetext import client
from .sublimetext import document
from .sublimetext import settings as python_settings
from .sublimetext import ServerOffline, ServerError

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)
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
        self.diagnostics = None

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
        self.workspace_directory = None
        self.diagnostics = None


class Settings:
    """SublimeText Settings handler"""

    def __init__(self):
        self.autocomplete = True
        self.documentation = True
        self.format_document = True
        self.linter = True

    def __repr__(self):
        return (
            "autocomplete :{autocomplete}, "
            "documentation: {documentation} "
            "format_document: {format_document} "
            "linter: {linter}"
            "".format(
                autocomplete=self.autocomplete,
                documentation=self.documentation,
                format_document=self.format_document,
                linter=self.linter,
            )
        )

    def load_settings(self):
        settings = sublime.load_settings("Pytools.sublime-settings")

        self.autocomplete = settings.get("autocomplete", True)
        self.documentation = settings.get("documentation", True)
        self.format_document = settings.get("format_document", True)
        self.linter = settings.get("linter", True)
        return settings

    def initialize(self) -> None:
        """initialize"""

        settings = self.load_settings()

        def interpreter_change():
            sublime.active_window().run_command("pytools_shutdownserver")

        settings.add_on_change("interpreter", interpreter_change)   # interpreter
        settings.add_on_change("autocomplete", self.load_settings)
        settings.add_on_change("documentation", self.load_settings)
        settings.add_on_change("format_document", self.load_settings)
        settings.add_on_change("linter", self.load_settings)

    def disable_all(self) -> None:
        """disable all services"""

        self.autocomplete = False
        self.documentation = False
        self.format_document = False
        self.linter = False


SERVER_STATE = StateManager()
SETTINGS = Settings()


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


def valid_attribute(view, pos):
    """attribute in valid scope"""

    result = all(
        [
            view.match_selector(pos, "source.python"),
            not view.match_selector(pos, "comment"),
            not view.match_selector(pos, "string"),
        ]
    )
    return result


@request_queue
def change_workspace(path_directory):
    """change workspace

    Raises:
        ServerOffline"""

    if SERVER_STATE.workspace_directory == path_directory:
        return
    logger.debug("change workspace")
    results = client.change_workspace(path_directory)
    SERVER_STATE.workspace_directory = results.results["workspace_directory"]
    return


class Diagnostic:
    """Diagnostic holder"""

    def __init__(self, severity: int, region: sublime.Region, message: str):
        self.severity = severity
        self.region = region
        self.message = message

    def __repr__(self):
        return ("severity: {severity}, region: {region}, " "message: {message}").format(
            severity=self.severity, region=self.region, message=self.message
        )

    @classmethod
    def from_rpc(cls, view, message):
        """build from rpc

        Raise:
            KeyError"""

        pos = view.text_point(message["line"] - 1, message["column"])
        region = view.line(pos) if message["column"] == 0 else view.word(pos)
        severity = message["severity"]
        msg = "%s: %s" % (message["code"], message["message"])
        return cls(severity, region, msg)


def status_message(message: str):
    """show message in status bar"""
    sublime.active_window().status_message(message)


class PyTools(sublime_plugin.EventListener):
    """Event based command"""

    def __init__(self):
        self.completion = None
        self.old_prefix = ""

        # completion cache
        self.cached_source = ""
        self.cached_completion = None

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

        source = view.substr(source_region)

        def fetch_completion(source, line, character):
            try:
                change_workspace(os.path.dirname(view.file_name()))
                results = client.fetch_completion(source, line, character)
            except ServerOffline:
                return None
            else:
                if results.error:
                    status_message(results.error)
                    return
                return results

        if self.cached_source == source:
            self.completion = self.cached_completion
        else:
            self.cached_source = source
            results = fetch_completion(source, line, character)
            self.completion = (
                [] if not results else list(make_completion(results.results))
            )
            self.cached_completion = self.completion

        document.show_completions(view)

    def on_query_completions(self, view, prefix, locations):
        """on query completion listener"""

        if not all(
            [
                valid_source(view),
                valid_attribute(view, locations[0]),
                SETTINGS.autocomplete,
            ]
        ):
            return None

        def build(completion):
            if not completion:
                return None
            return (
                completion,
                sublime.INHIBIT_WORD_COMPLETIONS | sublime.INHIBIT_EXPLICIT_COMPLETIONS,
            )

        if isinstance(self.completion, list):
            completion = self.completion if prefix.startswith(self.old_prefix) else None
            self.completion = None
            return build(completion)

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

        try:
            change_workspace(os.path.dirname(view.file_name()))
            results = client.fetch_documentation(
                view.substr(source_region), line, character
            )
        except ServerOffline:
            pass
        else:
            if results.error:
                status_message(results.error)
                return

            if not results.results:
                return  # cancel

            content = results.results.get("html")
            link = results.results.get("link")

            document.show_popup(
                view,
                decorate(content),
                location,
                lambda _: document.open_link(view, link),
            )

    def on_hover(self, view, point, hover_zone):
        """on hover listener"""

        if all(
            [
                valid_source(view),
                hover_zone == sublime.HOVER_TEXT,
                valid_attribute(view, point),
                SETTINGS.documentation,
            ]
        ):
            logger.debug("on hover")

            thread = threading.Thread(
                target=self.fetch_documentation, args=(view, point)
            )
            thread.start()

        elif all(
            [
                valid_source(view),
                hover_zone == sublime.HOVER_GUTTER,
                SERVER_STATE.diagnostics,
            ]
        ):

            def is_intersect(diagnostic: Diagnostic):
                return diagnostic.region.intersects(view.line(point))

            def get_message(diagnostic: Diagnostic):
                return diagnostic.message

            message = map(get_message, filter(is_intersect, SERVER_STATE.diagnostics))
            body = "<br>".join(message)
            if not body:  # empty
                return

            html_msg = '<div style="padding: 0.5em">{body}</div>'.format(body=body)
            logger.debug(html_msg)
            document.show_popup(view, html_msg, location=point, callback=None)

    def on_pre_save_async(self, view):
        if valid_source(view):
            view.run_command("pytools_clean_diagnose")


class PytoolsFormatCommand(sublime_plugin.TextCommand):
    """Formatting command"""

    def run(self, edit):
        if all([valid_source(self.view), SETTINGS.format_document]):
            self.format_document(self.view, edit)

    @server_valid
    def format_document(self, view, edit):

        src = view.substr(sublime.Region(0, view.size()))
        try:
            results = client.format_code(src)
        except ServerOffline:
            pass
        else:
            if results.error:
                status_message(results.error)
                return
            logger.debug(results)
            document.apply_changes(view, edit, results.results)

    def is_visible(self):
        return valid_source(self.view)


class PytoolsDiagnoseCommand(sublime_plugin.TextCommand):
    """Diagnose command"""

    def run(self, edit, path=None):
        view = self.view
        if not all([valid_source(view), SETTINGS.linter]):
            return  # any False

        view.window().run_command("pytools_clean_diagnose")
        module_path = view.file_name() if not path else path
        thread = threading.Thread(target=self.diagnose, args=(view, module_path))
        thread.start()

    @server_valid
    def diagnose(self, view, path):
        try:
            results = client.get_diagnostic(path)
        except ServerOffline:
            pass
        else:
            logger.debug(results)

            if results.error:
                status_message(results.error)
                return

            def build_diagnostic(messages):
                try:
                    for message in messages:
                        yield Diagnostic.from_rpc(view, message)

                except KeyError:
                    pass

            def sort_func(diagnostic: Diagnostic):
                return diagnostic.severity

            SERVER_STATE.diagnostics = list(
                sorted(build_diagnostic(results.results), key=sort_func, reverse=True)
            )

            scope = {1: "Invalid", 2: "Invalid", 3: "Comment", 4: "Comment"}
            icon = {1: "circle", 2: "dot", 3: "bookmark", 4: "bookmark"}
            flags = {
                1: sublime.DRAW_NO_OUTLINE,
                2: sublime.DRAW_NO_FILL
                | sublime.DRAW_NO_OUTLINE
                | sublime.DRAW_SOLID_UNDERLINE,
                3: sublime.DRAW_NO_FILL
                | sublime.DRAW_NO_OUTLINE
                | sublime.DRAW_SOLID_UNDERLINE
                | sublime.HIDE_ON_MINIMAP,
                4: sublime.DRAW_NO_FILL
                | sublime.DRAW_NO_OUTLINE
                | sublime.DRAW_SQUIGGLY_UNDERLINE
                | sublime.HIDE_ON_MINIMAP,
            }

            def mark(view, severity: int, regions: list):
                key = "pytools:%d" % severity

                view.add_regions(
                    key, regions, scope[severity], icon[severity], flags[severity]
                )

            def get_region(diagnostic: Diagnostic):
                return diagnostic.region

            for severity in [1, 2, 3, 4]:
                filtered = (
                    d for d in SERVER_STATE.diagnostics if d.severity == severity
                )
                regions = (get_region(d) for d in filtered)
                mark(view=view, severity=severity, regions=list(regions))

    def is_visible(self):
        return valid_source(self.view)


class PytoolsCleanDiagnoseCommand(sublime_plugin.TextCommand):
    """CleanDiagnose command"""

    def run(self, edit):
        for severity in [1, 2, 3, 4]:
            key = "pytools:%d" % severity
            SERVER_STATE.diagnostics = None
            self.view.erase_regions(key)


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
        python_path = subl_settings.get("interpreter")
        if not python_path:
            config = sublime.yes_no_cancel_dialog(
                "Python interpreter not configured.\nConfigure now?",
                no_title="Igore this session",
            )
            if config == sublime.DIALOG_YES:
                self.window.run_command("pytools_python_interpreter")
            elif config == sublime.DIALOG_NO:
                SETTINGS.disable_all()
            else:
                pass
            return

        thread = threading.Thread(target=self.run_server, args=(python_path,))
        thread.start()

    @process_lock
    def run_server(self, python_path):
        if SERVER_STATE.error:  # cancel all request if server error
            return

        activate_path = python_settings.find_activate(python_path)
        env_path = python_settings.find_environment(python_path)
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
        python_settings.set_interpreter(self.window)


class PytoolsStateinfoCommand(sublime_plugin.WindowCommand):
    """Load python interpreter command"""

    def run(self):
        print(SERVER_STATE)
        print(SETTINGS)


class PytoolsTestCommand(sublime_plugin.WindowCommand):
    """Load python interpreter command"""

    def run(self):
        print(SERVER_STATE)
        message = "Server required to perform autocomplete, documentation and formatting.\n\nRun server?"
        results = sublime.yes_no_cancel_dialog(
            msg=message, yes_title="Run", no_title="Ignore"
        )
        print(results)
