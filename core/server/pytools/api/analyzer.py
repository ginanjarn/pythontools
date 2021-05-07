"""diagnostic"""


from collections import namedtuple
import os
import re
import subprocess
import logging
from typing import List, Dict, Any


logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)
sh = logging.StreamHandler()
template = "%(asctime)s - %(levelname)s::%(module)s: %(lineno)d\t%(message)s"
sh.setFormatter(logging.Formatter(template))
sh.setLevel(logging.DEBUG)
logger.addHandler(sh)


def pylint(path: str, *, enable: List[str] = None, disable: List[str] = None) -> str:
    """lint with pylint"""

    pylint_cmd = [
        "pylint",
        "--exit-zero",
        "--score=n",
        # "--enable=%s" % ",".join(enable) if enable else "",
        # "--disable=%s" % ",".join(disable) if disable else "",
        "--msg-template='{C}:{msg_id}: {path}:{line}:{column}: {msg}'",
        path,
    ]

    logger.debug(pylint_cmd)

    env = os.environ.copy()

    try:
        if os.name == "nt":
            # STARTUPINFO only available on windows
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.SW_HIDE | subprocess.STARTF_USESHOWWINDOW
        else:
            startupinfo = None

        server_proc = subprocess.Popen(
            pylint_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,
            env=env,
            startupinfo=startupinfo,
        )

    except FileNotFoundError:
        raise ModuleNotFoundError("pylint") from None

    sout, serr = server_proc.communicate()
    if serr:
        raise Exception("\n".join(serr.decode().splitlines()))

    return sout.decode()


def pyflakes(path: str):
    """lint with pyflakes"""

    pyflakes_cmd = ["pyflakes", path]
    env = os.environ.copy()

    try:
        if os.name == "nt":
            # STARTUPINFO only available on windows
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.SW_HIDE | subprocess.STARTF_USESHOWWINDOW
        else:
            startupinfo = None

        server_proc = subprocess.Popen(
            pyflakes_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,
            env=env,
            startupinfo=startupinfo,
        )

    except FileNotFoundError:
        raise ModuleNotFoundError("pyflakes") from None

    sout, serr = server_proc.communicate()
    if serr:
        raise Exception("\n".join(serr.decode().splitlines()))

    return sout.decode()


# fmt: off

# SEVERITY

ERROR       = 1
WARNING     = 2
INFO        = 3
HINT        = 4

# fmt: on


def transform_severity(severity):
    code = {"F": ERROR, "E": ERROR, "W": WARNING, "C": INFO, "R": HINT}
    return code[severity]


def pylint_to_rpc(message: str):
    pattern = r"(\w):(\w*): (.*):(\d*):(\d*): (.*)"

    for line in message.splitlines():
        found = re.findall(pattern, line)
        if not any(found):
            logger.debug("not found from : '%s'", line)
            continue

        Diagnostic = namedtuple(
            "Diagnostic", ["severity", "msg_id", "path", "line", "column", "message"],
        )
        diagnose = Diagnostic(*found[0])
        yield {
            "severity": transform_severity(diagnose.severity),
            "code": diagnose.msg_id,
            "path": diagnose.path,
            "line": int(diagnose.line),
            "column": int(diagnose.column),
            "message": diagnose.message,
        }


def pyflakes_to_rpc(message: str):
    pattern = r"(.*):(\d*):(\d*)\s(.*)"

    for line in message.splitlines():
        found = re.findall(pattern, line)
        if not any(found):
            logger.debug("not found from : '%s'", line)
            continue

        Diagnostic = namedtuple("Diagnostic", ["path", "line", "column", "message"])
        diagnose = Diagnostic(*found[0])
        yield {
            "severity": WARNING,
            "code": "WARNING",
            "path": diagnose.path,
            "line": int(diagnose.line),
            "column": int(diagnose.column),
            "message": diagnose.message,
        }


class PyLint:
    def __init__(self, path: str):
        self.message = pylint(path)

    def to_rpc(self) -> Dict[str, Any]:
        return list(pylint_to_rpc(self.message))


class PyFlakes:
    def __init__(self, path: str):
        self.message = pyflakes(path)

    def to_rpc(self) -> Dict[str, Any]:
        return list(pyflakes_to_rpc(self.message))


def lint(path: str, *, engine="pylint"):
    """lint module"""

    # lint engine map
    lint_func = {"pylint": PyLint, "pyflakes": PyFlakes}
    diagnostic = lint_func[engine](path)

    return diagnostic.to_rpc()
