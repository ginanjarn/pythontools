"""Main plugin"""


import sublime  # pylint: disable=import-error
import sublime_plugin  # pylint: disable=import-error
import threading
import logging
import os
import time
from .core.sublimetext import client
from .core.sublimetext import document
from .core.sublimetext import settings as python_settings

# from .core.sublimetext import ServerOffline, ServerError, InvalidInput

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
sh = logging.StreamHandler()
sh.setFormatter(logging.Formatter("%(levelname)s\t%(module)s: %(lineno)d\t%(message)s"))
sh.setLevel(logging.DEBUG)
fh = logging.FileHandler(os.path.join(os.path.dirname(__file__), "plugins.log"))
fh.setFormatter(logging.Formatter("%(levelname)s\t%(module)s: %(lineno)d\t%(message)s"))
fh.setLevel(logging.ERROR)
logger.addHandler(sh)
logger.addHandler(fh)


INSTANCE_LOCK = threading.Lock()
REQUEST_LOCK = threading.RLock()


def instance_lock(func):
    def wrapper(*args, **kwargs):
        if INSTANCE_LOCK.locked():
            logger.debug("instance locked")
            return None
        with INSTANCE_LOCK:
            return func(*args, **kwargs)

    return wrapper


def request_lock(func):
    def wrapper(*args, **kwargs):
        with REQUEST_LOCK:
            return func(*args, **kwargs)

    return wrapper


SETTINGS_BASENAME = "Pytools.sublime-settings"


def feature_enabled(feature_name: str, *, default=False) -> bool:
    sublime_settings = sublime.load_settings(SETTINGS_BASENAME)
    return sublime_settings.get(feature_name, default)


class ServerCapability(dict):
    """server capability"""


SERVER_ONLINE = False


def set_offline(status=True):
    global SERVER_ONLINE

    SERVER_ONLINE = not status


def check_connection():
    # global SERVER_ONLINE
    try:
        client.ping()
    except client.ServerOffline:
        # SERVER_ONLINE = False
        set_offline()
    else:
        # SERVER_ONLINE = True
        set_offline(False)


INITIALIZED = False


@request_lock
def initialize():
    logger.info("initialize")

    global SERVER_ONLINE
    global INITIALIZED

    if INITIALIZED:
        return
    try:
        result = client.initialize()
    except client.ServerOffline:
        # SERVER_ONLINE = False
        logger.debug("ServerOffline")
        set_offline()
        INITIALIZED = False
    else:
        # SERVER_ONLINE = True
        logger.debug("ServerOnline")
        set_offline(False)
        INITIALIZED = True
    finally:
        logger.debug("SERVER_ONLINE : %s, INITIALIZED : %s", SERVER_ONLINE, INITIALIZED)


WORKSPACE_DIRECTORY = None


@request_lock
def change_workspace(directory_path) -> None:
    logger.info("on change workspace")
    global WORKSPACE_DIRECTORY
    if directory_path != WORKSPACE_DIRECTORY:
        result = client.change_workspace(directory_path)
        if result.results:
            WORKSPACE_DIRECTORY = result.results["workspace_directory"]
            logger.debug("WORKSPACE_DIRECTORY = %s", WORKSPACE_DIRECTORY)


def valid_source(view, pos=0):
    """python source file"""

    return view.match_selector(pos, "source.python")


def valid_attribute(view, pos):
    """attribute in valid scope"""

    result = all(
        [
            view.match_selector(pos, "source.python"),
            not view.match_selector(pos, "source.python comment"),
            not view.match_selector(pos, "source.python meta.string.python string"),
        ]
    )
    return result


SERVER_ERROR = False


class PytoolsPythonInterpreterCommand(sublime_plugin.WindowCommand):
    """Load python interpreter command"""

    def run(self):
        try:
            python_settings.set_interpreter(self.window)
        except Exception:
            logger.error("set interpreter", exc_info=True)


class PytoolsRunserverCommand(sublime_plugin.WindowCommand):
    """Run server command"""

    @instance_lock
    def run(self):
        logger.info("on run server")

        if SERVER_ERROR:
            logger.debug("server error")
            return  # cancel if server error

        sublime_settings = sublime.load_settings("Pytools.sublime-settings")
        python_path = sublime_settings.get("interpreter")
        if not python_path:
            config = sublime.ok_cancel_dialog(
                "Python interpreter not configured.\nConfigure now?",
            )
            if config:
                self.window.run_command("pytools_python_interpreter")
            # else:
            # SETTINGS.disable_all()
            # TODO: HANDLE ON IGNORE ------------------------------------------
            return

        thread = threading.Thread(target=self.run_server, args=(python_path,))
        thread.start()

    def run_server(self, python_path):
        # if SERVER_STATE.error:  # cancel all request if server error
        # return

        activate_path = python_settings.find_activate(python_path)
        env_path = python_settings.find_environment(python_path)
        server_path = os.path.dirname(os.path.abspath(__file__))
        # server_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "core")
        server_module = "core.server"
        activate_path = [path for path in (activate_path, env_path) if path]

        global SERVER_ERROR

        try:
            logger.debug("running server")
            logger.debug("%s, %s, %s", server_path, server_module, activate_path)
            client.run_server(server_path, server_module, activate_path=activate_path)
            # SERVER_STATE.online = True
        except client.ServerError:
            logger.debug("server error")
            # SERVER_STATE.error = True
            # SERVER_STATE.online = False
            SERVER_ERROR = True
        except Exception:
            logger.error("run server", exc_info=True)
        else:
            logger.debug("server ready")
            self.window.status_message("Server ready")
            # self.window.active_view().run_command("pytools_change_workspace")
            # initialize_server()
            time.sleep(0.5)
            initialize()


class PytoolsShutdownserverCommand(sublime_plugin.WindowCommand):
    """Shutdown command"""

    @instance_lock
    def run(self):
        logger.info("on shutdown server")
        logger.debug("init shutdown server")
        thread = threading.Thread(target=self.exit)
        thread.start()

    @request_lock
    def exit(self):
        # if SERVER_STATE.error:  # cancel all request if server error
        if SERVER_ERROR:  # cancel all request if server error
            return
        try:
            response = client.shutdown()
        except client.ServerOffline:
            set_offline()
            logger.debug("ServerOffline")
            pass
        except Exception:
            logger.error("shutdown server", exc_info=True)
        else:
            set_offline()
            # SERVER_STATE.reset()
            logger.debug("finish shutdown server")


def start_server(func):
    def wrapper(*args, **kwargs):
        if SERVER_ONLINE:
            return func(*args, **kwargs)
        if SERVER_ERROR:
            logger.debug("ServerError")
            return None
        logger.debug(
            "SERVER_ONLINE : %s, SERVER_ERROR : %s", SERVER_ONLINE, SERVER_ERROR
        )
        sublime.active_window().run_command("pytools_runserver")
        return None

    return wrapper


def plugin_loaded():
    thread = threading.Thread(target=check_connection)
    thread.start()
    # TODO: HANDLE ON SETTINGS CHANGE --------------------------------------------


class Event(sublime_plugin.ViewEventListener):
    def __init__(self, view):
        self.view = view

        self.completion = None

        self.cached_completion = None
        self.temp_completion_src = ""
        self.cached_docstring = None
        self.temp_docstring_src = ""

    @staticmethod
    def build_completion(completions: "Iterable") -> "Iterator[Any, Any]":
        """build completion"""

        for completion in completions:
            yield (
                "%s  \t%s" % (completion["label"], completion["type"]),
                completion["label"],
            )

    @start_server
    @instance_lock
    @request_lock
    def fetch_completions(self, prefix, location):
        view = self.view

        start = 0
        end = location
        word_region = view.word(location)
        if view.substr(word_region).isidentifier() and len(prefix) > 1:
            end = word_region.a  # complete at first identifier offset
        source_region = sublime.Region(start, end)
        line, character = view.rowcol(end)  # get rowcol at end selection

        source = view.substr(source_region)

        if self.temp_completion_src == source:
            self.completion = self.cached_completion
            return None
        else:
            try:
                initialize()
                work_dir = os.path.dirname(view.file_name())
                change_workspace(work_dir)
                result = client.fetch_completion(source, line, character)
            except client.ServerOffline:
                set_offline()
                logger.debug("ServerOffline")
                return None
            else:
                if result.error:
                    logger.info(result.error)
                    return None
                self.temp_completion_src = source
                self.cached_completion = (
                    list(self.build_completion(result.results)),
                    sublime.INHIBIT_WORD_COMPLETIONS
                    | sublime.INHIBIT_EXPLICIT_COMPLETIONS,
                )
                self.completion = self.cached_completion

        document.show_completions(view)

    # @instance_lock
    def on_query_completions(self, prefix, locations):
        logger.info("on query completions")
        view = self.view
        if all(
            [
                valid_source(view),
                valid_attribute(view, locations[0]),
                feature_enabled("autocomplete", default=True),
            ]
        ):
            if self.completion:
                completion = self.completion
                self.completion = None
                return completion

            thread = threading.Thread(
                target=self.fetch_completions, args=(prefix, locations[0])
            )
            thread.start()

    @staticmethod
    def decorate(content) -> str:
        """decorate popup content"""
        return '<div style="padding: .5em">%s</div>' % content

    @start_server
    @instance_lock
    @request_lock
    def fetch_documentation(self, location):
        """fetch documentation thread"""

        view = self.view

        start = 0
        word_region = view.word(location)
        if view.substr(word_region).isidentifier():
            end = word_region.b  # select until end of word
        else:
            return  # cancel request for non identifier
        source_region = sublime.Region(start, end)
        source = view.substr(source_region)

        line, character = view.rowcol(end)  # get rowcol at end selection

        content, link = None, None

        if self.temp_docstring_src == source:
            content, link = self.cached_docstring
        else:
            try:
                initialize()
                work_dir = os.path.dirname(view.file_name())
                change_workspace(work_dir)

                result = client.fetch_documentation(
                    view.substr(source_region), line, character
                )
                logger.debug(result)
            except client.ServerOffline:
                set_offline()
                logger.debug("ServerOffline")
                pass
            except Exception:
                logger.error("fetch documentation", exc_info=True)
            else:
                if result.error:
                    logger.debug("documentation error:\n%s", result.error)
                    return

                logger.debug("result = %s", result.results)
                if not result.results:
                    return  # cancel

                content = result.results.get("html")
                link = result.results.get("link")

                self.temp_docstring_src = source
                self.cached_docstring = (content, link)

            if content:
                document.show_popup(
                    view,
                    self.decorate(content),
                    location,
                    lambda _: document.open_link(view, link),
                )

    # @instance_lock
    def on_hover(self, point, hover_zone):
        logger.info("on hover")
        view = self.view
        if all(
            [
                valid_source(view),
                valid_attribute(view, point),
                feature_enabled("documentation", default=True),
                hover_zone == sublime.HOVER_TEXT,
            ]
        ):

            thread = threading.Thread(target=self.fetch_documentation, args=(point,))
            thread.start()


class PytoolsFormatCommand(sublime_plugin.TextCommand):
    """Formatting command"""

    @start_server
    @instance_lock
    def run(self, edit):
        logger.info("on format document")
        view = self.view
        if all([valid_source(view), feature_enabled("format_document", default=True)]):

            source = view.substr(sublime.Region(0, view.size()))
            try:
                results = client.format_code(source)
            except client.ServerOffline:
                set_offline()
                logger.debug("ServerOffline")
                pass
            except Exception:
                logger.error("format document", exc_info=True)
            else:
                if results.error:
                    return
                logger.debug(results)
                document.apply_changes(view, edit, results.results)

    def is_visible(self):
        return valid_source(self.view)


class PytoolsStateinfoCommand(sublime_plugin.WindowCommand):
    """Shutdown command"""

    def run(self):
        print("SERVER_ONLINE : %s, SERVER_ERROR : %s" % (SERVER_ONLINE, SERVER_ERROR))
