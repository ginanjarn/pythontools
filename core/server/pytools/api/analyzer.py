"""diagnostic"""


from collections import namedtuple
import os
import re
import subprocess
import logging
from typing import List


logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)
sh = logging.StreamHandler()
sh.setFormatter(logging.Formatter("%(levelname)s\t%(module)s: %(lineno)d\t%(message)s"))
sh.setLevel(logging.DEBUG)
logger.addHandler(sh)


class PylintMessage(str):
    """Pylint message"""


class PyflakesMessage(str):
    """Pyflakes message"""


def pylint(path: str, *, enable: List[str] = None, disable: List[str] = None) -> str:
    """pylint"""

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
            # linux subprocess module does not have STARTUPINFO
            # so only use it if on Windows
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.SW_HIDE | subprocess.STARTF_USESHOWWINDOW
            server_proc = subprocess.Popen(
                pylint_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=True,
                env=env,
                startupinfo=si,
            )
        else:
            server_proc = subprocess.Popen(
                pylint_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=True,
                env=env,
            )

    except FileNotFoundError:
        raise ModuleNotFoundError("pylint") from None

    sout, serr = server_proc.communicate()
    if serr:
        raise Exception("\n".join(serr.decode().splitlines()))

    return PylintMessage(sout.decode())


def pyflakes(path):
    """lint with pyflakes"""

    pyflakes_cmd = ["pyflakes", path]
    env = os.environ.copy()

    try:
        if os.name == "nt":
            # linux subprocess module does not have STARTUPINFO
            # so only use it if on Windows
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.SW_HIDE | subprocess.STARTF_USESHOWWINDOW
            server_proc = subprocess.Popen(
                pyflakes_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=True,
                env=env,
                startupinfo=si,
            )
        else:
            server_proc = subprocess.Popen(
                pyflakes_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=True,
                env=env,
            )

    except FileNotFoundError:
        raise ModuleNotFoundError("pyflakes") from None

    sout, serr = server_proc.communicate()
    if serr:
        raise Exception("\n".join(serr.decode().splitlines()))

    return PyflakesMessage(sout.decode())


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


def pylint_to_rpc(message):
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


def pyflakes_to_rpc(message):
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


def to_rpc(message: str) -> "Dict[str, Any]":
    """convert message to rpc"""

    return (
        list(pylint_to_rpc(message))
        if isinstance(message, PylintMessage)
        else list(pyflakes_to_rpc(message))
    )


def lint(path: str, *, engine="pylint"):
    """lint module"""

    # lint engine map
    lint_func = {"pylint": pylint, "pyflakes": pyflakes}
    results = lint_func[engine](path)

    return results
