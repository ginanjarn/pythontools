"""Main plugin"""


import sublime  # pylint: disable=import-error
import sublime_plugin  # pylint: disable=import-error
import threading
import logging
import os
import time
from contextlib import contextmanager
from functools import wraps
from itertools import dropwhile
from .core import client
from .core.sublimetext import document
from .core.sublimetext import interpreter
from .core.sublimetext import plugin_settings


logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)
sh = logging.StreamHandler()
template = "%(asctime)s - %(levelname)s::%(module)s: %(lineno)d\t%(message)s"
sh.setFormatter(logging.Formatter(template))
sh.setLevel(logging.DEBUG)
logger.addHandler(sh)

INSTANCE_LOCK = threading.Lock()
BOUNDARY_LOCK = threading.RLock()


def instance_lock(func):
    """instance lock

    prevent run multiple instance
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        if INSTANCE_LOCK.locked():
            logger.debug("instance locked")
            return None

        key = "PROCESS_LOCK"
        view = sublime.active_window().active_view()
        view.set_status(key, "BUSY")
        with INSTANCE_LOCK:
            result = func(*args, **kwargs)
        view.erase_status(key)
        return result

    return wrapper


def boundary_lock(func):
    """request lock

    prevent multiple request from outer context
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        with BOUNDARY_LOCK:
            return func(*args, **kwargs)

    return wrapper


@contextmanager
def load_settings(name, *, save=False):
    sublime_settings = sublime.load_settings(name)
    yield sublime_settings

    if save:
        sublime.save_settings(name)


# All features enabled
ALL_ENABLED = False


def feature_enabled(feature_name: str, *, default=True) -> bool:
    """check if feature enabled on settings"""

    with load_settings(plugin_settings.SETTINGS_BASENAME) as sublime_settings:
        return sublime_settings.get(feature_name, default) and ALL_ENABLED


SERVER_ONLINE = False


def set_offline(offline=True):
    """set server state offline"""

    global SERVER_ONLINE

    SERVER_ONLINE = not offline

    if offline:  # bool
        uninitialize()


class ServerCapability(dict):
    """server capability"""


SERVER_CAPABILITY = ServerCapability()


def server_capable(feature_name: str, *, default=False) -> bool:
    """check if server capable perform feature"""

    return SERVER_CAPABILITY.get(feature_name, default)


INITIALIZED = False


@boundary_lock
def initialize():
    """initialize server"""

    logger.info("initialize")

    global INITIALIZED

    if INITIALIZED:
        return

    try:
        result = client.initialize()

    except client.ServerOffline as err:
        logger.debug(err)
        set_offline()

    else:
        logger.debug("ServerOnline")
        set_offline(False)  # online

        if result.error:
            logger.debug("server initialize error : %s", repr(result.error))
            return

        INITIALIZED = True

        set_capability(result.results)
        sublime.status_message("READY")

    finally:
        logger.debug("SERVER_ONLINE : %s, INITIALIZED : %s", SERVER_ONLINE, INITIALIZED)


# fmt: off

# RPC FEATURE capability
COMPLETION_CAPABILITY          = "completion"
HOVER_CAPABILITY               = "hover"
DOCUMENT_FORMATTING_CAPABILITY = "document_format"
DIAGNOSTIC_CAPABILITY          = "diagnostic"
VALIDATE_CAPABILITY            = "validate"
RENAME_CAPABILITY              = "rename"

# fmt: on


def set_capability(capability):

    global SERVER_CAPABILITY

    # apply capability
    SERVER_CAPABILITY[plugin_settings.F_AUTOCOMPLETE] = capability.get(
        COMPLETION_CAPABILITY, False
    )
    SERVER_CAPABILITY[plugin_settings.F_DOCUMENTATION] = capability.get(
        HOVER_CAPABILITY, False
    )
    SERVER_CAPABILITY[plugin_settings.F_DOCUMENT_FORMATTING] = capability.get(
        HOVER_CAPABILITY, False
    )
    SERVER_CAPABILITY[plugin_settings.F_DIAGNOSTIC] = capability.get(
        DIAGNOSTIC_CAPABILITY, False
    )
    SERVER_CAPABILITY[plugin_settings.F_VALIDATE] = capability.get(
        VALIDATE_CAPABILITY, False
    )
    SERVER_CAPABILITY[plugin_settings.F_RENAME] = capability.get(
        RENAME_CAPABILITY, False
    )
    logger.debug(SERVER_CAPABILITY)


WORKSPACE_DIRECTORY = None


def change_workspace(directory_path) -> None:
    """change workspace directory"""

    logger.info("on change workspace")

    global WORKSPACE_DIRECTORY

    if directory_path != WORKSPACE_DIRECTORY:
        result = client.change_workspace(directory_path)
        if result.results:
            WORKSPACE_DIRECTORY = result.results["workspace_directory"]
            logger.debug("WORKSPACE_DIRECTORY = %s", repr(WORKSPACE_DIRECTORY))

            sublime.status_message("Workspace : %s" % WORKSPACE_DIRECTORY)


def uninitialize():
    """unitialize server"""

    logger.info("uninitialize")
    global SERVER_ONLINE
    global INITIALIZED
    global SERVER_CAPABILITY
    global WORKSPACE_DIRECTORY

    SERVER_ONLINE = False
    INITIALIZED = False
    SERVER_CAPABILITY.clear()
    WORKSPACE_DIRECTORY = None


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

INTERPRETER_SETTING_KEY = "interpreter"


class PytoolsPythonInterpreterCommand(sublime_plugin.WindowCommand):
    """Load python interpreter command"""

    def run(self):
        try:
            self.set_interpreter(self.window)
        except Exception:
            logger.error("set interpreter", exc_info=True)

    def set_interpreter(self, window: "sublime.Window") -> None:
        """set python interpreter"""

        sys_python = interpreter.find_python()
        conda = interpreter.find_conda()
        python_paths = list(sys_python) + list(conda)
        python_binaries = [
            os.path.join(path, interpreter.PYTHON_BIN) for path in python_paths
        ]

        def input_path():
            def on_done(path):
                self.save_interpreter_path(path)

            window.show_input_panel(
                caption="python path",
                initial_text="",
                on_done=on_done,
                on_change=None,
                on_cancel=None,
            )

        def select_interpreter(index=-1):
            if index < 0:
                return  # cancel if index == -1

            if index < len(python_paths):
                self.save_interpreter_path(python_binaries[index])

            else:
                input_path()

        selected_index = -1

        with load_settings(plugin_settings.SETTINGS_BASENAME) as sublime_settings:
            active_interpreter = sublime_settings.get(INTERPRETER_SETTING_KEY)
            try:
                selected_index = python_binaries.index(active_interpreter)
            except ValueError:
                logger.debug("saved active interpreter not found")

        window.show_quick_panel(
            items=python_binaries + ["input path"],
            on_select=select_interpreter,
            selected_index=selected_index,
            flags=sublime.KEEP_OPEN_ON_FOCUS_LOST | sublime.MONOSPACE_FONT,
        )

    def save_interpreter_path(self, path):
        if not interpreter.is_python_path(path):
            sublime.error_message("Invalid python path:\n%s" % path)
            return

        with load_settings(
            plugin_settings.SETTINGS_BASENAME, save=True
        ) as sublime_settings:
            sublime_settings.set(INTERPRETER_SETTING_KEY, path)


class PytoolsRunserverCommand(sublime_plugin.WindowCommand):
    """Run server command"""

    def run(self):
        logger.info("on run server")

        if SERVER_ERROR:
            logger.debug("server error")
            return  # cancel if server error

        with load_settings(plugin_settings.SETTINGS_BASENAME) as sublime_settings:
            python_path = sublime_settings.get(INTERPRETER_SETTING_KEY)

            if not python_path:
                config = sublime.ok_cancel_dialog(
                    "Python interpreter not configured.\nConfigure now?",
                )

                if config:
                    self.window.run_command("pytools_python_interpreter")

                else:
                    # disable all feature if python interpreter not configured
                    global ALL_ENABLED
                    ALL_ENABLED = False

                # cancel start thread
                return

            thread = threading.Thread(target=self.run_server, args=(python_path,))
            thread.start()

    @instance_lock
    @boundary_lock
    def run_server(self, python_path):
        """run server thread"""

        plugin_path = os.path.dirname(os.path.abspath(__file__))
        activate_path = interpreter.find_activate(python_path)
        env_path = interpreter.find_environment(python_path)

        server_path = os.path.join(plugin_path, "core", "server", "pytools",)
        activate_path = [path for path in (activate_path, env_path) if path]

        try:
            logger.debug("running server")
            logger.debug("%s, %s", server_path, activate_path)

            @boundary_lock
            def runserver():
                client.run_server(server_path, activate_path=activate_path)

            # run server
            runserver()

            sublime.status_message("SERVER RUNNING")

        except client.ServerError as err:
            logger.debug(err)

            global SERVER_ERROR
            SERVER_ERROR = True

        except client.PortInUse:
            # continue initialize if server already running
            self.initialize_server()

        except Exception:
            logger.error("run server", exc_info=True)

        else:
            # continue initialize if server already running
            self.initialize_server()

    @staticmethod
    def initialize_server(timeout=30):
        """try to initialize server"""

        def try_initialize():
            terminate_time = time.time() + timeout

            while time.time() < terminate_time:
                if INITIALIZED:
                    # terminate
                    return

                logger.debug("try initialize")
                initialize()

                # continue
                if not INITIALIZED:
                    time.sleep(0.5)

            # raise TimeoutError if not terminated
            raise TimeoutError("timedout")

        try:
            try_initialize()

        except TimeoutError:
            # set server error if failed initialize
            global SERVER_ERROR
            SERVER_ERROR = True
            logger.error("ServerError: unable to initialize")


class PytoolsShutdownserverCommand(sublime_plugin.WindowCommand):

    """Shutdown command"""

    def run(self):
        logger.info("on shutdown server")

        thread = threading.Thread(target=self.exit)
        thread.start()

    @instance_lock
    def exit(self):

        try:
            response = client.shutdown()
        except client.ServerOffline as err:
            set_offline()
            logger.debug(err)

        except Exception:
            logger.error("shutdown server", exc_info=True)

        else:
            set_offline()

        finally:
            logger.debug("finish shutdown server")
            sublime.status_message("SERVER TERMINATED")


def config_preferences():
    with load_settings("Python.sublime-settings", save=True) as sublime_settings:
        sublime_settings.set("index_files", False)
        sublime_settings.set("auto_complete_use_index", False)
        sublime_settings.set("translate_tabs_to_spaces", True)
        sublime_settings.set("show_definitions", False)
        sublime_settings.set("tab_completion", False)


def plugin_loaded():
    """on plugin loaded

    sublime definition for plugin_loaded event
    """

    config_preferences()

    # Enable default on loaded
    global ALL_ENABLED
    ALL_ENABLED = True

    thread = threading.Thread(target=initialize)
    thread.start()


def project_path(view: sublime.View):

    file_name = view.file_name()
    if not file_name:
        return None

    try:
        path = max(
            (
                folder
                for folder in view.window().folders()
                if file_name.startswith(folder)
            )
        )

    except ValueError:
        return os.path.dirname(file_name)
    else:
        return path


ACTIVE_PROJECT = ""


def set_active_project():
    """set project path to active view"""

    global ACTIVE_PROJECT
    view = sublime.active_window().active_view()
    ACTIVE_PROJECT = project_path(view)


# Diagnostic data holder
DIAGNOSTICS = []

# output panel name
OUTPUT_PANEL_NAME = "pytools"


class CompletionParams:
    def __init__(self, start, end):
        self.start = start
        self.end = end

    @classmethod
    def from_view(cls, view: sublime.View, location: int):
        """Build from view

        Params:
            view(sublime.View): current view
            location(int): cursor position

        Raises:
            ValueError
        """
        word_region = view.word(location)

        start = 0
        prefix = view.substr(word_region).rstrip()

        def access_member(word_region):
            return view.substr(sublime.Region(word_region.a - 1, word_region.a)) == "."

        if prefix.isidentifier():
            if word_region.size() > 1:
                end = word_region.a + 1
            else:
                end = location

            if access_member(word_region):
                logger.debug("access member")
                end = word_region.a
        else:
            # only next to dot -> access member
            if prefix.endswith(".", 0, 1):
                end = location
            else:
                raise ValueError("invalid prefix to complete")

        return cls(start=start, end=end)


class Completion:
    def __init__(self, completions: "Optional[List[Tuple[str, str]]]" = None):

        self.completions = completions if completions else []
        self._completion_results = [completion[1] for completion in self.completions]

    def is_completed(self, prefix):
        return prefix in self._completion_results

    def to_sublime(self):
        return (
            self.completions,
            sublime.INHIBIT_WORD_COMPLETIONS | sublime.INHIBIT_EXPLICIT_COMPLETIONS,
        )

    @staticmethod
    def build_completion(completions: "Iterable[str, Any]") -> "Iterator[Any, Any]":
        for completion in completions:
            yield (
                "%s  \t%s" % (completion["label"], completion["type"]),
                completion["label"],
            )

    @classmethod
    def from_rpc(cls, params: "List[str, Any]"):
        return cls(list(Completion.build_completion(params)))


# plugin only enabled on python source
PLUGIN_ENABLED = False


class RequirementInvalid(Exception):
    """invalid required input"""


class Event(sublime_plugin.ViewEventListener):
    """Event handler"""

    def __init__(self, view):

        self.view = view

        self.completion = None

        self.old_end_position = None
        self.cached_completion = None
        self.temp_completion_src = ""
        self.cached_docstring = None
        self.temp_docstring_src = ""

        # cache_diagnostic hold filtered diagnostic result for active view
        self.cached_diagnostic = None

    @staticmethod
    def build_completion(completions: "Iterable") -> "Iterator[Any, Any]":
        """build completion"""

        for completion in completions:
            yield (
                "%s  \t%s" % (completion["label"], completion["type"]),
                completion["label"],
            )

    @instance_lock
    def fetch_completions(self, prefix, params: CompletionParams):
        """fetch completion process"""

        view = self.view
        line, character = view.rowcol(params.end)  # get rowcol at end selection
        source_region = sublime.Region(params.start, params.end)
        source = view.substr(source_region)

        if self.temp_completion_src == source:
            logger.debug("using cache")
            self.completion = self.cached_completion
        else:
            try:
                initialize()

                if not ACTIVE_PROJECT:
                    set_active_project()

                change_workspace(ACTIVE_PROJECT)

                result = client.fetch_completion(source, line, character)

            except client.ServerOffline as err:
                set_offline()
                logger.debug(err)
                return

            else:
                if result.error:
                    logger.info(result.error)
                    return

                self.completion = Completion.from_rpc(result.results)

                # set cache
                self.temp_completion_src = source
                self.cached_completion = self.completion

        self.old_end_position = params.end
        document.show_completions(view)

    def on_query_completions(self, prefix, locations):
        """on_query_completion event"""

        if not PLUGIN_ENABLED:
            return None

        logger.info("on query completions")
        view = self.view

        if not SERVER_ONLINE:
            view.window().run_command("pytools_runserver")
            return None

        def check_requirements():
            """if requirements valid

            Raises:
                RequirementInvalid
            """

            if not feature_enabled(plugin_settings.F_AUTOCOMPLETE):
                raise RequirementInvalid(
                    "feature disabled: %s" % repr(plugin_settings.F_AUTOCOMPLETE)
                )

            if not server_capable(plugin_settings.F_AUTOCOMPLETE):
                raise RequirementInvalid(
                    "server incapable: %s" % repr(plugin_settings.F_AUTOCOMPLETE)
                )

            if not valid_attribute(view, locations[0]):
                raise RequirementInvalid("invalid scope")

        empty_completion = Completion()

        try:
            check_requirements()
            location = max(view.sel()[0].a, locations[0])
            params = CompletionParams.from_view(view, location)

        except ValueError as err:
            logger.debug(err)
            document.hide_completions(view)
            return empty_completion.to_sublime()

        except RequirementInvalid as err:
            logger.debug(err)
            return None

        else:
            logger.debug("prefix = %s", repr(prefix))
            if self.completion:
                completion = self.completion
                self.completion = None

                # invalid context
                if self.old_end_position != params.end:
                    logger.debug(
                        "invalid context: %s != %s", self.old_end_position, params.end
                    )
                    document.hide_completions(view)
                    return empty_completion.to_sublime()

                if completion.is_completed(prefix):
                    logger.debug("already completed")
                    document.hide_completions(view)
                    return empty_completion.to_sublime()

                logger.debug("show completion results")
                return completion.to_sublime()

            thread = threading.Thread(
                target=self.fetch_completions, args=(prefix, params)
            )
            thread.start()
            return empty_completion.to_sublime()

    def decorate(self, content) -> str:
        """decorate popup content"""
        return '<div style="padding: .5em">%s</div>' % content

    @instance_lock
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

        content, link = None, None  # cache holder

        # is updating popup content
        is_updating = False

        if self.temp_docstring_src == source:
            logger.debug("use cached docstring : %s", self.cached_docstring)
            content, link = self.cached_docstring

            is_updating = True

        else:
            try:
                initialize()

                if not ACTIVE_PROJECT:
                    set_active_project()

                change_workspace(ACTIVE_PROJECT)

                result = client.fetch_documentation(
                    view.substr(source_region), line, character
                )
                logger.debug(result)

            except client.ServerOffline as err:
                set_offline()
                logger.debug(err)

            except Exception:
                logger.error("fetch documentation", exc_info=True)

            else:
                if result.error:  # any error
                    return  # cancel

                if not result.results:  # empty results
                    return  # cancel

                content = result.results.get("html")
                link = result.results.get("link")

                # set cache
                self.temp_docstring_src = source
                self.cached_docstring = (content, link)

        if content:  # any content
            document.show_popup(
                view,
                self.decorate(content),
                location,
                lambda _: document.open_link(view, link),
                update=is_updating,
            )

    def on_hover(self, point, hover_zone):
        """on_hover event"""

        if not PLUGIN_ENABLED:
            return

        view = self.view

        def check_docstring_requirements():

            if not feature_enabled(plugin_settings.F_DOCUMENTATION):
                raise RequirementInvalid(
                    "feature disabled: %s" % repr(plugin_settings.F_DOCUMENTATION)
                )

            if not server_capable(plugin_settings.F_DOCUMENTATION):
                raise RequirementInvalid(
                    "server incapable: %s" % repr(plugin_settings.F_DOCUMENTATION)
                )

            if not valid_attribute(view, point):
                raise RequirementInvalid("invalid scope")

            if point == view.size():
                raise RequirementInvalid("out of range")

        def hover_text():
            logger.info("on get documentation")

            if not SERVER_ONLINE:
                view.window().run_command("pytools_runserver")
                return

            try:
                check_docstring_requirements()
            except RequirementInvalid as err:
                logger.debug(err)
                return
            else:
                thread = threading.Thread(
                    target=self.fetch_documentation, args=(point,)
                )
                thread.start()

        def check_lint_message_requirements():
            if not DIAGNOSTICS:
                raise RequirementInvalid("no any diagnostics message")

            if not valid_source(view):
                raise RequirementInvalid("invalid source")

            if not any(
                [
                    feature_enabled(plugin_settings.F_DIAGNOSTIC),
                    feature_enabled(plugin_settings.F_VALIDATE),
                ]
            ):
                raise RequirementInvalid("feature disabled")

        def hover_gutter():
            logger.info("on show diagnostic")

            try:
                check_lint_message_requirements()

            except RequirementInvalid as err:
                logger.debug(err)

            else:
                if not self.cached_diagnostic:
                    diagnostic_message = document.diagnostic_message(DIAGNOSTICS, view)
                    self.cached_diagnostic = diagnostic_message

                row, _ = view.rowcol(point)
                content = self.cached_diagnostic.get(row)
                logger.debug("loaded : %s", content)

                if content:  # any content
                    document.show_popup(
                        view, self.decorate(content), point, callback=None, update=True
                    )

        if hover_zone == sublime.HOVER_TEXT:
            hover_text()
        elif hover_zone == sublime.HOVER_GUTTER:
            hover_gutter()

    def clear_cached_diagnostic(self):
        if self.cached_diagnostic:
            self.cached_diagnostic = None

    def on_modified(self):

        if not PLUGIN_ENABLED:
            return

        self.clear_cached_diagnostic()
        view = self.view
        prefix = view.substr(view.word(view.sel()[0].a))

        # hide completion if prefix not identifier
        if not str.isidentifier(prefix) and view.is_auto_complete_visible():
            document.hide_completions(view)

    def on_activated(self):

        global PLUGIN_ENABLED

        if valid_source(self.view):
            PLUGIN_ENABLED = True
            set_active_project()
            self.clear_cached_diagnostic()

            if logger.level == logging.NOTSET or logger.level > logging.INFO:
                self.view.run_command("pytools_show_diagnostic_panel")

        else:
            PLUGIN_ENABLED = False

    def on_pre_close(self):

        if not PLUGIN_ENABLED:
            return

        self.view.run_command("pytools_clear_diagnostic")

    def on_pre_save_async(self) -> None:

        if not PLUGIN_ENABLED:
            return

        self.clear_cached_diagnostic()
        self.view.run_command("pytools_clear_diagnostic")

    def on_post_save_async(self) -> None:

        if not PLUGIN_ENABLED:
            return

        if valid_source(self.view):
            path = self.view.file_name()
            self.view.run_command(
                "pytools_diagnostic", args={"quick": True, "path": path}
            )


class PytoolsFormatCommand(sublime_plugin.TextCommand):
    """Formatting command"""

    def run(self, edit):

        if not PLUGIN_ENABLED:
            return

        logger.info("on format document")

        view = self.view
        if not SERVER_ONLINE:
            view.window().run_command("pytools_runserver")
            return

        def check_requirements():

            if not feature_enabled(plugin_settings.F_DOCUMENT_FORMATTING):
                raise RequirementInvalid(
                    "feature disabled: %s" % repr(plugin_settings.F_DOCUMENT_FORMATTING)
                )

            if not server_capable(plugin_settings.F_DOCUMENT_FORMATTING):
                raise RequirementInvalid(
                    "server incapable: %s" % repr(plugin_settings.F_DOCUMENT_FORMATTING)
                )

            if not valid_source(view):
                raise RequirementInvalid("invalid source")

        try:
            check_requirements()

        except RequirementInvalid as err:
            logger.debug(err)

        else:
            source = view.substr(sublime.Region(0, view.size()))
            file_name = view.file_name()

            thread = threading.Thread(
                target=self.formatting_task, args=(view, file_name, source)
            )
            thread.start()

    @instance_lock
    def formatting_task(self, view: sublime.View, path: str, source: str):
        logger.debug("on formatting thread")

        try:
            result = client.format_code(source)
            logger.debug(result)

        except client.ServerOffline as err:
            set_offline()
            logger.debug(err)

        except Exception:
            logger.error("format document", exc_info=True)

        else:
            output_panel = document.OutputPanel(view.window(), OUTPUT_PANEL_NAME)

            if result.error:  # any error
                logger.debug(result.error)
                output_panel.append(result.error["message"])
                output_panel.show()
                return

            output_panel.hide()

            window = sublime.active_window()

            if window.active_view().id() != view.id():
                view = window.open_file(path)

            view.run_command(
                "pytools_apply_rpc_change", args={"changes": result.results}
            )

    def is_visible(self):
        return valid_source(self.view)


class PytoolsDiagnosticCommand(sublime_plugin.TextCommand):
    """Diagnostic command"""

    PYFLAKES = "validate"
    PYLINT = "diagnose"

    @boundary_lock
    def run(self, edit, path=None, quick=False):

        if not PLUGIN_ENABLED:
            return

        logger.info("on diagnostic")

        # clear current diagnostic
        self.view.run_command("pytools_clear_diagnostic")

        view = self.view
        if not path:
            file_name = view.file_name()
            path = file_name if file_name else ""

        def check_requirement(feature):
            if not feature_enabled(feature):
                raise RequirementInvalid("feature disabled : %s" % feature)

            if not server_capable(feature):
                raise RequirementInvalid("server incapable : %s" % feature)

            if os.path.isdir(path):
                # path is directory
                pass

            elif os.path.isfile(path):
                # path is file

                from re import findall

                if not any(findall(r".*\.py[ic]?", path)):
                    # file is not python file
                    sublime.error_message("Unable lint non-python file !")
                    raise RequirementInvalid("not python file")

            else:
                # invalid path
                raise RequirementInvalid("invalid path : %s" % path)

        try:
            if quick:
                check_requirement(plugin_settings.F_VALIDATE)
                method = PytoolsDiagnosticCommand.PYFLAKES

            else:
                check_requirement(plugin_settings.F_DIAGNOSTIC)
                method = PytoolsDiagnosticCommand.PYLINT

        except RequirementInvalid as err:
            logger.debug("input error : %s", repr(err))

        else:
            thread = threading.Thread(target=self.diagnose, args=(method, path,))
            thread.start()

    @instance_lock
    def diagnose(self, lint_method, path):
        logger.debug("on diagnostic thread")
        logger.debug("target : %s", path)

        lint_functions = {
            PytoolsDiagnosticCommand.PYFLAKES: client.analyzer.validate,
            PytoolsDiagnosticCommand.PYLINT: client.analyzer.get_diagnostic,
        }

        try:
            result = lint_functions[lint_method](path)

        except client.ServerOffline as err:
            logger.debug(err)

        else:
            output_panel = document.OutputPanel(self.view.window(), OUTPUT_PANEL_NAME)

            if result.error:  # any error
                logger.debug(result.error)
                output_panel.append(result.error["message"])
                output_panel.show()
                return

            output_panel.hide()

            global DIAGNOSTICS

            diagnostics = []
            for diagnostic in result.results:
                diagnostics.append(document.Mark.from_rpc(self.view, diagnostic))

            logger.debug(diagnostics)
            DIAGNOSTICS.extend(diagnostics)
            document.mark_document(self.view, DIAGNOSTICS)

            self.view.run_command("pytools_show_diagnostic_panel")

    def is_visible(self):
        return valid_source(self.view)


class PytoolsShowDiagnosticPanelCommand(sublime_plugin.TextCommand):
    """diagnostic panel"""

    def run(self, edit):

        if not PLUGIN_ENABLED:
            return

        if feature_enabled(plugin_settings.W_DIAGNOSTIC_PANEL):
            self.show_diagnostic_panel()

    def show_diagnostic_panel(self):
        filtered_diagnostics = [
            diagnostic
            for diagnostic in DIAGNOSTICS
            if diagnostic.view_id == self.view.id()
        ]

        window = sublime.active_window()
        view = window.active_view()

        def build_message(diagnostics):
            for diagnostic in diagnostics:
                message = diagnostic.message
                row, col = view.rowcol(diagnostic.region.a)
                file_name = os.path.basename(view.file_name())
                yield "{file_name}:{row}:{col}: {message}".format(
                    file_name=file_name, row=row + 1, col=col, message=message
                )

        output_panel = document.OutputPanel(window, OUTPUT_PANEL_NAME)

        if filtered_diagnostics:
            output_panel.append(*build_message(filtered_diagnostics))
            output_panel.show()

        else:
            output_panel.hide()


class PytoolsClearDiagnosticCommand(sublime_plugin.TextCommand):
    """Diagnostic command"""

    def run(self, edit):

        if not PLUGIN_ENABLED:
            return

        logger.info("on clear diagnostic")

        window = sublime.active_window()
        view = window.active_view()  # active document view
        if not valid_source(view):
            return

        for severity in [
            document.ERROR,
            document.WARNING,
            document.INFO,
            document.HINT,
        ]:
            document.erase_regions(view, document.KEY_FORMAT % severity)

        global DIAGNOSTICS

        def removed(mark: document.Mark):
            return mark.view_id == view.id()

        DIAGNOSTICS = list(dropwhile(removed, DIAGNOSTICS))

        # destroy output panel
        output_panel = document.OutputPanel(window, OUTPUT_PANEL_NAME)
        output_panel.destroy()

    def is_visible(self):
        return valid_source(self.view)


class PytoolsRenameCommand(sublime_plugin.TextCommand):
    """Diagnostic command"""

    def run(self, edit):

        if not PLUGIN_ENABLED:
            return

        logger.info("on rename")

        try:
            INSTANCE_LOCK.acquire()
            self.rename()

        except RequirementInvalid as err:
            logger.debug("rename error: %s", err)

        finally:
            INSTANCE_LOCK.release()

    def rename(self):
        """Perform rename

        Raises:
            RequirementInvalid
        """

        view = self.view

        if not feature_enabled(plugin_settings.F_RENAME):
            raise RequirementInvalid(
                "feature disabled %s" % repr(plugin_settings.F_RENAME)
            )

        if not server_capable(plugin_settings.F_RENAME):
            raise RequirementInvalid(
                "server incapable %s" % repr(plugin_settings.F_RENAME)
            )

        if any([v for v in sublime.active_window().views() if v.is_dirty()]):
            sublime.error_message(
                (
                    "Error !\n\nUnable rename unsaved document. "
                    "Save all documents before perform rename."
                )
            )
            raise RequirementInvalid("unable rename unsaved view")

        selection = view.sel()[0]

        if not valid_attribute(view, selection.a):
            raise RequirementInvalid("invalid attribute")

        self.target_identifier = view.substr(selection)

        if selection.size() != view.word(selection.a).size():
            raise RequirementInvalid(
                "invalid attribute %s" % repr(self.target_identifier)
            )

        self.path = view.file_name()
        self.offset = selection.a

        document.show_input_panel(
            view.window(),
            "rename: %s to " % repr(self.target_identifier),
            initial_text=self.target_identifier,
            on_done=self.on_input_name_done,
        )

    def on_input_name_done(self, new_name):
        thread = threading.Thread(
            target=self.rename_thread, args=(self.path, self.offset, new_name)
        )
        thread.start()

    @instance_lock
    def rename_thread(self, path: str, offset: int, new_name: str):
        try:
            if new_name == self.target_identifier:
                raise RequirementInvalid("nothing changed")

            if not str.isidentifier(new_name):
                raise RequirementInvalid("invalid new name %s" % repr(new_name))

            set_active_project()
            change_workspace(ACTIVE_PROJECT)

            result = client.rename(file_path=path, offset=offset, new_name=new_name)

        except client.ServerOffline as err:
            logger.debug(err)

        except RequirementInvalid as err:
            logger.debug(err)

        except Exception:
            logger.error("rename error", exc_info=True)

        else:
            if result.error:
                logger.debug(result.error)

            else:
                # apply changes
                logger.debug(result.results)
                PytoolsRenameCommand.apply_renames(result.results)

    def is_visible(self):
        return valid_source(self.view)

    @staticmethod
    def apply_renames(changes: "Dict[str, Any]"):
        window = sublime.active_window()

        def update_document(change):
            view = window.open_file(change["file_name"])

            # make sure if document loaded
            retry = 0.0
            while True:
                if view.is_loading():
                    time.sleep(0.5)
                    retry += 0.5
                    continue

                if retry >= 30.0:  # max wait 30 second
                    raise Exception("unable load file")
                break

            view.run_command(
                "pytools_apply_rpc_change", args={"changes": change["changes"]}
            )

        def rename_document(change):
            old_name = change["changes"]["old_name"]
            new_name = change["changes"]["new_name"]

            path_type = "directory" if os.path.isdir(old_name) else ""
            if sublime.ok_cancel_dialog(
                "Would you line rename %s:\n\n  %s\n  to:\n  %s"
                % (path_type, old_name, new_name)
            ):
                os.rename(old_name, new_name)
                if os.path.isfile(new_name):
                    window.open_file(new_name)

        for change in changes:
            try:
                if change["type"] == "change":
                    update_document(change)

                elif change["type"] == "rename":
                    rename_document(change)

            except (KeyError, FileNotFoundError):
                logger.error("error apply_renames", exc_info=True)


class PytoolsApplyRpcChangeCommand(sublime_plugin.TextCommand):
    """Diagnostic command"""

    def run(self, edit, changes):
        document.apply_changes(self.view, edit, changes)


class PytoolsStateinfoCommand(sublime_plugin.WindowCommand):
    """Shutdown command"""

    def run(self):
        print("PLUGIN_ENABLED : %s" % PLUGIN_ENABLED)
        print(
            "SERVER_ONLINE : %s, SERVER_ERROR : %s, SERVER_CAPABILITY : %s"
            % (SERVER_ONLINE, SERVER_ERROR, SERVER_CAPABILITY)
        )
        print("WORKSPACE_DIRECTORY : %s" % WORKSPACE_DIRECTORY)
        print("DIAGNOSTICS : %s" % DIAGNOSTICS)
