"""Settings handler"""


import os
import re


PATH_BIN = "Scripts" if os.name == "nt" else "bin"
PYTHON_BIN = "python.exe" if os.name == "nt" else os.path.join(PATH_BIN, "python")
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
