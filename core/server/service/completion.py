"""Completion module"""


from jedi.api import Completion  # type: ignore
from jedi import Script, Project  # type: ignore
from typing import Dict, Any, List, Iterator
import logging

logger = logging.getLogger("formatting")
logger.setLevel(logging.DEBUG)
sh = logging.StreamHandler()
sh.setFormatter(logging.Formatter("%(levelname)s\t%(module)s: %(lineno)d\t%(message)s"))
sh.setLevel(logging.DEBUG)
logger.addHandler(sh)



def get_project(path: str) -> "Project":
    """get project property"""
    return Project(path)


def to_rpc(completions: "List[Completion]") -> "Dict[str,Any]":
    """convert completion results to rpc"""

    def build_rpc(completions: "Completion") -> "Dict[str, Any]":
        for completion in completions:
            yield {"label": completion.name_with_symbols, "type": completion.type}

    return list(build_rpc(completions))


def complete(source: str, line: int, column: int, **kwargs) -> "Any":
    """complete script at following pos(line, column)"""
    project = kwargs.get("project", None)
    path = kwargs.get("path","")
    logger.debug(project)
    script = Script(code=source, path=path, project=project)
    results = script.complete(line=line, column=column)
    raw = kwargs.get("raw", None)
    return to_rpc(results) if not raw else results
