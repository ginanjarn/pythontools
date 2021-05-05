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
    from jedi.api.classes import Completion as JediCompletion  # type: ignore

    preload_module(["numpy", "tensorflow", "wx"])

    def build_rpc(completions: List[JediCompletion]) -> Iterator[Dict[str, Any]]:
        """build rpc content"""

        for completion in completions:
            yield rpc.CompletionItem.builder(
                label=completion.name_with_symbols, type_=completion.type
            )

    def to_rpc(completions: List[JediCompletion]) -> List[Dict[str, Any]]:
        """convert completion results to rpc"""

        return list(build_rpc(completions))

    class Completion:
        def __init__(
            self, source: str, *, line: int, column: int, project: Project = None
        ):
            script = Script(source, project=project)
            self.candidates = script.complete(line, column)

        def to_rpc(self):
            return to_rpc(self.candidates)


except ImportError:
    print("module 'jedi' not installed, code completion may not available")
