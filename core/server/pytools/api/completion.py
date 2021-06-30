"""Completion module"""


from typing import Dict, Any, List, Iterator, Optional
from html import escape
import logging

from api import rpc, errors


logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)
sh = logging.StreamHandler()
template = "%(asctime)s - %(levelname)s::%(module)s: %(lineno)d\t%(message)s"
sh.setFormatter(logging.Formatter(template))
sh.setLevel(logging.DEBUG)
logger.addHandler(sh)


try:
    from jedi import Script, Project, preload_module  # type: ignore
    from jedi.api.classes import Completion as JediCompletion  # type: ignore

    preload_module(["numpy", "tensorflow", "wx"])

    def document_body(docs: Optional[str]) -> str:
        """build documentation body"""
        return escape(docs, quote=False) if docs else ""

    def get_signatures(completion: JediCompletion):
        signatures = completion.get_signatures()
        return signatures[0].to_string() if signatures else ""

    def build_rpc(completions: List[JediCompletion]) -> Iterator[Dict[str, Any]]:
        """build rpc content"""

        for completion in completions:

            completion_type = completion.type

            doc = (
                document_body(get_signatures(completion))
                if completion_type in ["class", "function"]
                else ""
            )

            yield rpc.CompletionItem.builder(
                label=completion.name_with_symbols,
                type_=completion_type,
                documentation=doc,
            )

    def to_rpc(completions: List[JediCompletion]) -> List[Dict[str, Any]]:
        """convert completion results to rpc"""

        return list(build_rpc(completions))

    class Completion:
        def __init__(
            self, source: str, *, line: int, column: int, project: Project = None
        ):
            script = Script(source, project=project)
            try:
                self.candidates = script.complete(line, column)
            except ValueError as err:
                raise errors.InvalidInput(str(err)) from err

        def to_rpc(self):
            return to_rpc(self.candidates)


except ImportError:
    print("module 'jedi' not installed, code completion may not available")
