"""Settings handler"""


import sublime  # pylint: disable=import-error
import os
import re


def save_settings(key, value):
    settings = sublime.load_settings("Pytools.sublime-settings")
    settings.set(key, value)
    sublime.save_settings("Pytools.sublime-settings")


PYTHON_BIN = "python.exe" if os.name == "nt" else os.path.join("bin", "python")
PATH_BIN = "Scripts" if os.name == "nt" else "bin"


def ispython_path(path):
    """check if python path"""
    return os.path.isfile(os.path.join(path, PYTHON_BIN))


def find_python():
    """find python in path"""
    for path in os.environ["PATH"].split(os.pathsep):
        if ispython_path(path):
            yield path


def any_match_conda(name):
    """any match *conda* character"""
    return any(re.findall(r"\s*conda.*", name))


def find_conda_envs(conda_directory):
    """get conda envs"""
    envs_path = os.path.join(conda_directory, "envs")
    for env_directory in os.listdir(envs_path):
        env_path = os.path.join(envs_path, env_directory)
        if ispython_path(env_path):
            yield env_path


def find_conda():
    """find any conda installed in path"""
    home = os.path.expanduser("~")
    for directory in os.listdir(home):
        path = os.path.join(home, directory)
        if any_match_conda(directory) and ispython_path(path):
            yield path
            yield from find_conda_envs(path)


def find_activate(python_path):
    """find environment activator"""

    def find_path(dir_path: str):
        activate_path = "Scripts\\activate" if os.name == "nt" else r"bin/activate"
        paths = dir_path.split(os.sep)

        for root in range(len(paths)):
            prefix = os.sep.join(paths[:root])
            path = os.path.join(prefix, activate_path)
            if os.path.isfile(path):
                return path

        raise FileNotFoundError("unable find `activate` file")

    return find_path(python_path)


def find_environment(python_path):
    """find environment path"""

    def find_path(dir_path: str):
        paths = dir_path.split(os.sep)

        for root in range(len(paths), 0, -1):  # find from latest path
            prefix = os.sep.join(paths[:root])
            path = os.path.join(prefix, PYTHON_BIN)
            if os.path.isfile(path):
                return prefix

        raise FileNotFoundError("unable find `python` file")

    return find_path(python_path)


def set_interpreter(window):
    sys_python = find_python()
    conda = find_conda()
    python_path = list(sys_python) + list(conda)
    python_binary = [os.path.join(ipr, PYTHON_BIN) for ipr in python_path]

    def input_path():
        def save_input_settings(path):
            if ispython_path(path):
                save_settings("path", path)

        window.show_input_panel(
            caption="python path",
            initial_text="",
            on_done=save_input_settings,
            on_change=None,
            on_cancel=None,
        )

    def select_interpreter(index):
        if index < 0:
            return  # cancel if index == -1

        if index < len(python_path):
            save_settings("path", python_binary[index])
        else:
            input_path()

    window.show_quick_panel(
        items=python_binary + ["input path"],
        on_select=select_interpreter,
        flags=sublime.KEEP_OPEN_ON_FOCUS_LOST | sublime.MONOSPACE_FONT,
    )
