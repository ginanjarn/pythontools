"""Completion module"""


from jedi import Script, Project  # type: ignore
from jedi.api.classes import Completion  # type: ignore
from typing import Dict, Any, List, Iterator
import logging

logger = logging.getLogger("formatting")
# logger.setLevel(logging.DEBUG)
sh = logging.StreamHandler()
sh.setFormatter(logging.Formatter("%(levelname)s\t%(module)s: %(lineno)d\t%(message)s"))
sh.setLevel(logging.DEBUG)
logger.addHandler(sh)


def build_rpc(completions: List[Completion]) -> Iterator[Dict[str, Any]]:
    """build rpc content"""

    for completion in completions:
        yield {"label": completion.name_with_symbols, "type": completion.type}


def to_rpc(completions: List[Completion]) -> List[Dict[str, Any]]:
    """convert completion results to rpc"""

    return list(build_rpc(completions))


def complete(
    source: str, *, line: int, column: int, project: Project = None
) -> List[Completion]:
    """complete script at following pos(line, column)

    Raises:
        ValueError: column > len(line_content)
    """

    script = Script(code=source, project=project)
    results = script.complete(line=line, column=column)
    return results
