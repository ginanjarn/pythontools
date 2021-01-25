"""document formatting module"""


import subprocess
import os
import re
import logging

logger = logging.getLogger("formatting")
logger.setLevel(logging.DEBUG)
sh = logging.StreamHandler()
sh.setFormatter(logging.Formatter("%(levelname)s\t%(module)s: %(lineno)d\t%(message)s"))
sh.setLevel(logging.DEBUG)
logger.addHandler(sh)


def format_with_black(source: str) -> str:
    """format document with black

    Result:
        diff changes
    """

    black_cmd = ["python", "-m", "black", "--diff", "-"]
    env = os.environ.copy()

    if os.name == "nt":
        # linux subprocess module does not have STARTUPINFO
        # so only use it if on Windows
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.SW_HIDE | subprocess.STARTF_USESHOWWINDOW
        server_proc = subprocess.Popen(
            black_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,
            env=env,
            startupinfo=si,
        )
    else:
        server_proc = subprocess.Popen(
            black_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,
            env=env,
        )

    sout, serr = server_proc.communicate(source.encode())
    if server_proc.returncode == 123:
        raise ValueError(serr.decode().replace(os.sep, "\n"))
    elif server_proc.returncode == 1:
        raise ModuleNotFoundError("module not found : black")

    return sout.decode()


def to_rpc(changes: str, old_source: str):
    """convert changes to rpc"""

    def get_removed(line: str) -> "Tuple[int,int]":
        """get zero based removed line"""
        found = re.findall(r"@@ \-(\d*),?(\d*)\s.*@@", line)
        if not any(found):
            raise ValueError("unable to parse diff header", line)
        start_str = found[0][0]
        span_str = found[0][1]
        start = int(start_str) - 1
        span = int(span_str) - 2 if span_str else 0
        end = start + span
        return start, end

    def change_object(changes: str, old_source: str):
        old_lines = old_source.splitlines()
        change_lines = changes.splitlines()
        for line in change_lines:
            if line.startswith("@@"):
                # get removed line
                start, end = get_removed(line)
                # get removed start line offset
                start_character = 0
                # get removed end line offset
                end_character = len(old_lines[end])
                yield {
                    "range": {
                        "start": {"line": start, "character": start_character},
                        "end": {"line": end, "character": end_character},
                    },
                    "newText": "",
                }
            elif line.startswith("-"):
                continue
            else:
                yield line[1:]

    rpc_change, index = [], -1

    for change in change_object(changes, old_source):
        if isinstance(change, dict):
            rpc_change.append(change)
            index += 1
        else:
            if not rpc_change:
                continue
            else:
                rpc_change[index]["newText"] = "\n".join(
                    [rpc_change[index]["newText"], change]
                )

    return rpc_change


def format_document(source: str, **kwargs) -> "Dict[str, Any]":
    """format document"""
    doc_changes = format_with_black(source)
    raw = kwargs.get("raw", None)
    return to_rpc(doc_changes, source) if not raw else doc_changes
