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
    logger.debug("return code = %s", server_proc.returncode)
    logger.debug("==> STDOUT\n%s", sout.decode())
    logger.debug("==> STDERR\n%s", serr.decode())

    if server_proc.returncode != 0:
        raise Exception(serr.decode())

    return sout.decode()


def transform_severity(severity):
    code = {"F": 1, "E": 1, "W": 2, "C": 3, "R": 4}
    return code[severity]


def to_rpc(message: str) -> "Dict[str, Any]":
    """convert message to rpc"""
    pattern = r"(\w):(\w*): (.*):(\d*):(\d*): (.*)"

    def parse(message):
        for line in message.splitlines():
            found = re.findall(pattern, line)
            if not any(found):
                logger.debug("not found from : '%s'", line)
                continue

            Diagnostic = namedtuple(
                "Diagnostic",
                ["severity", "msg_id", "path", "line", "column", "message"],
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

    return list(parse(message))


def lint(path: str, **kwargs):
    """lint module"""

    results = pylint(path)

    raw = kwargs.get("raw", None)
    return to_rpc(results) if not raw else results
