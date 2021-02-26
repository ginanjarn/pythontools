"""document formatting module"""


import subprocess
import os
import re
import logging

logger = logging.getLogger("formatting")
# logger.setLevel(logging.DEBUG)
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


def to_rpc(changes_diff: str, old_source: str):
    """convert changes to rpc"""

    def get_removed(line: str) -> "Tuple[int,int]":
        """get diff removed line"""
        found = re.findall(r"@@ \-(\d*),?(\d*)\s.*@@", line)
        if not any(found):
            raise ValueError("unable to parse diff header", line)
        start_str = found[0][0]
        span_str = found[0][1]
        start = int(start_str)
        span = int(span_str) - 1 if span_str else 0
        end = start + span
        return start, end

    def change_gen(changes_diff, old_source):
        olds = old_source.split("\n")
        for line in changes_diff.splitlines():
            if line.startswith("@@"):
                start_line, end_line = get_removed(line)
                logger.debug(line)
                yield {
                    "range": {
                        "start": {"line": start_line, "character": 0},
                        "end": {"line": end_line, "character": len(olds[end_line - 1])},
                    }
                }
            elif line.startswith("-"):
                continue
            elif line.startswith("+"):
                yield line[1:]
            elif line.startswith(" "):
                yield line[1:]
            else:
                continue

    changes = []
    index = -1
    for change in change_gen(changes_diff, old_source):
        if isinstance(change, dict):
            changes.append(change)
            index += 1
        else:
            if not changes:  # for list
                continue
            new_text = changes[index].get("newText")
            if new_text is None:
                changes[index]["newText"] = change
            else:
                changes[index]["newText"] = "\n".join([new_text, change])
    return changes


def format_document(source: str, **kwargs) -> "Dict[str, Any]":
    """format document"""
    doc_changes = format_with_black(source)
    raw = kwargs.get("raw", None)
    return to_rpc(doc_changes, source) if not raw else doc_changes