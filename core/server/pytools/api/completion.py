"""Completion module"""


from typing import Dict, Any, List, Iterator
import logging

from api import rpc


logger = logging.getLogger("formatting")
# logger.setLevel(logging.DEBUG)
sh = logging.StreamHandler()
sh.setFormatter(logging.Formatter("%(levelname)s\t%(module)s: %(lineno)d\t%(message)s"))
sh.setLevel(logging.DEBUG)
logger.addHandler(sh)


try:
    from jedi import Script, Project, preload_module  # type: ignore
    from jedi.api.classes import Completion  # type: ignore

    preload_module(["numpy", "tensorflow", "wx"])

    class Completions(list):
        """completion list"""

    def build_rpc(completions: List[Completion]) -> Iterator[Dict[str, Any]]:
        """build rpc content"""

        for completion in completions:
            yield rpc.CompletionItem.builder(
                label=completion.name_with_symbols, type_=completion.type
            )

    def to_rpc(completions: List[Completion]) -> List[Dict[str, Any]]:
        """convert completion results to rpc"""

        return list(build_rpc(completions))

    def complete(
        source: str, *, line: int, column: int, project: Project = None
    ) -> Completions:
        """complete script at following pos(line, column)

        Raises:
            ValueError: column > len(line_content)
        """

        script = Script(code=source, project=project)
        results = script.complete(line=line, column=column)
        return Completions(results)


except ImportError:
    print("module 'jedi' not installed, code completion may not available")
