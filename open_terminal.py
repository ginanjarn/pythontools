import sublime
import sublime_plugin
import os
import subprocess
from contextlib import contextmanager
from .core.sublimetext import interpreter


@contextmanager
def load_settings(name, save=False):
    settings = sublime.load_settings(name)
    yield settings
    if save:
        sublime.save_settings(name)


class TerminalOption:
    def __init__(self, cwd=None, activate_cmd=None):
        self.cwd = cwd
        self.activate_cmd = activate_cmd


TERMINAL_SETTINGS_KEY = "terminal"

TERMINAL_EMULATOR = {
    "nt": ["powershell.exe", "cmd.exe"],
    "posix": ["gnome-terminal", "xterm"],
}


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


class PytoolsOpenTerminalHere(sublime_plugin.WindowCommand):
    def run(self):
        path = os.path.dirname(self.window.active_view().file_name())
        self.window.run_command("pytools_open_terminal", {"path": path})


class PytoolsOpenTerminal(sublime_plugin.WindowCommand):
    def run(self, terminal_emulator=None, path=""):

        view = self.window.active_view()

        if not os.path.isdir(path):
            path = project_path(view)

        with load_settings("Pytools.sublime-settings") as sublime_settings:

            workdir = path
            activate_cmd = None

            if view.match_selector(0, "source.python"):

                python_path = sublime_settings.get("interpreter")
                activate_path = interpreter.find_activate(python_path)
                env_path = interpreter.find_environment(python_path)

                activate_cmd = "{activate_path} {env_path}".format(
                    activate_path=activate_path, env_path=env_path
                )

            self.terminal_option = TerminalOption(
                cwd=workdir, activate_cmd=activate_cmd,
            )

            terminal = (
                terminal_emulator
                if terminal_emulator
                else sublime_settings.get(TERMINAL_SETTINGS_KEY)
            )

            if not terminal:

                window = self.window
                window.show_quick_panel(
                    TERMINAL_EMULATOR[os.name],
                    flags=sublime.KEEP_OPEN_ON_FOCUS_LOST,
                    on_select=self.set_terminal_executable,
                )

            else:
                self.open_terminal(terminal)

    def set_terminal_executable(self, index=-1):
        if index < 0:
            return

        emulator = TERMINAL_EMULATOR[os.name][index]

        with load_settings("Pytools.sublime-settings", save=True) as sublime_settings:
            sublime_settings.set(TERMINAL_SETTINGS_KEY, emulator)

        self.open_terminal(emulator)

    def open_terminal(self, emulator: str):

        exec_command = [emulator]

        if os.name == "nt" and emulator.startswith("cmd"):
            exec_command.append("/K")

        option = self.terminal_option

        if self.terminal_option.activate_cmd and not emulator.startswith("powershell"):
            exec_command.append(option.activate_cmd)

        try:
            subprocess.Popen(exec_command, cwd=option.cwd)
        except OSError as err:
            sublime.error_message(str(err))
