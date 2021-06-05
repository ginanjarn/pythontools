"""Settings handler"""


import os
import re


PATH_BIN = "Scripts" if os.name == "nt" else "bin"
PYTHON_BIN = "python.exe" if os.name == "nt" else os.path.join(PATH_BIN, "python")
ACTIVATE_BIN = os.path.join(PATH_BIN, "activate")


def is_python_path(path) -> bool:

    return all(
        [any(re.findall(r".*python[23w]?(?:\.exe)?$", path)), os.path.isfile(path)]
    )


def is_activate_path(path) -> bool:

    return all([any(re.findall(r".*activate(?:\.bat)?$", path)), os.path.isfile(path)])


def find_python() -> "Iterator[str]":
    """find python installed in PATH"""

    for path in os.environ["PATH"].split(os.pathsep):
        if is_python_path(os.path.join(path, PYTHON_BIN)):
            yield path


def any_match_conda(name: str) -> bool:
    """any match *conda* character"""

    return any(re.findall(r"\s*conda.*", name))


def is_conda_dir(path):
    return any(re.findall(r".*conda.*", path)) and os.path.isfile(
        os.path.join(path, PYTHON_BIN)
    )


def find_conda_envs(conda_directory: str) -> "Iterator[str]":
    """get conda envs"""

    envs_path = os.path.join(conda_directory, "envs")
    for env_directory in os.listdir(envs_path):
        env_path = os.path.join(envs_path, env_directory)
        if is_python_path(os.path.join(env_path, PYTHON_BIN)):
            yield env_path


def find_conda() -> "Iterator[str]":
    """find conda installed in PATH"""

    home = os.path.expanduser("~")
    for directory in os.listdir(home):
        path = os.path.join(home, directory)
        if is_conda_dir(path):
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
        if is_activate_path(path):
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
        if is_python_path(os.path.join(prefix, PYTHON_BIN)):
            return prefix  # path found

    # else
    raise FileNotFoundError("unable find `python` file")
