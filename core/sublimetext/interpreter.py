"""Settings handler"""


import sublime  # pylint: disable=import-error
import os
import re


def save_settings(key: str, value: "Any") -> None:
    """save settings to SublimeText settings file"""

    settings = sublime.load_settings("Pytools.sublime-settings")
    settings.set(key, value)
    sublime.save_settings("Pytools.sublime-settings")


PYTHON_BIN = "python.exe" if os.name == "nt" else os.path.join("bin", "python")
PATH_BIN = "Scripts" if os.name == "nt" else "bin"
ACTIVATE_BIN = os.path.join(PATH_BIN, "activate")


def ispython_path(path: str) -> bool:
    """check if python path"""

    return os.path.isfile(os.path.join(path, PYTHON_BIN))


def find_python() -> "Iterable[str]":
    """find python installed in PATH"""

    for path in os.environ["PATH"].split(os.pathsep):
        if ispython_path(path):
            yield path


def any_match_conda(name: str) -> bool:
    """any match *conda* character"""

    return any(re.findall(r"\s*conda.*", name))


def find_conda_envs(conda_directory: str) -> "Iterable[str]":
    """get conda envs"""

    envs_path = os.path.join(conda_directory, "envs")
    for env_directory in os.listdir(envs_path):
        env_path = os.path.join(envs_path, env_directory)
        if ispython_path(env_path):
            yield env_path


def find_conda() -> "Iterable[str]":
    """find conda installed in PATH"""

    home = os.path.expanduser("~")
    for directory in os.listdir(home):
        path = os.path.join(home, directory)
        if any_match_conda(directory) and ispython_path(path):
            yield path
            yield from find_conda_envs(path)


def find_activate(python_path: str) -> str:
    """find environment activator

    Raises:
        FileNotFoundError
    """

    paths = python_path.split(os.sep)

    for root in range(len(paths)):
        prefix = os.sep.join(paths[:root])
        path = os.path.join(prefix, ACTIVATE_BIN)
        if os.path.isfile(path):
            return path  # path found

    # else
    raise FileNotFoundError("unable find `activate` file")


def find_environment(python_path: str) -> str:
    """find environment path

    Raises:
        FileNotFoundError
    """

    paths = python_path.split(os.sep)

    for root in range(len(paths), 0, -1):  # find from latest path
        prefix = os.sep.join(paths[:root])
        path = os.path.join(prefix, PYTHON_BIN)
        if os.path.isfile(path):
            return prefix  # path found

    # else
    raise FileNotFoundError("unable find `python` file")


def set_interpreter(window: "sublime.Window") -> None:
    """set python interpreter"""

    sys_python = find_python()
    conda = find_conda()
    python_path = list(sys_python) + list(conda)
    python_binary = [os.path.join(path, PYTHON_BIN) for path in python_path]

    def input_path():
        def save_input_settings(path):
            if ispython_path(path):
                save_settings("interpreter", path)

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
            save_settings("interpreter", python_binary[index])
        else:
            input_path()

    window.show_quick_panel(
        items=python_binary + ["input path"],
        on_select=select_interpreter,
        flags=sublime.KEEP_OPEN_ON_FOCUS_LOST | sublime.MONOSPACE_FONT,
    )
