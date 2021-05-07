"""Hover module"""


from typing import List, Dict, Any, Optional
from html import escape
import logging

from api import rpc


logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)
sh = logging.StreamHandler()
template = "%(asctime)s - %(levelname)s::%(module)s: %(lineno)d\t%(message)s"
sh.setFormatter(logging.Formatter(template))
sh.setLevel(logging.DEBUG)
logger.addHandler(sh)


try:
    from jedi import Script, Project, preload_module
    from jedi.api.classes import BaseName

    preload_module(["numpy", "tensorflow", "wx"])

    def escape_space(doc: str) -> str:
        """replace 'double space' -> '&nbsp;'"""
        return doc.replace("  ", "&nbsp;&nbsp;")

    def escape_newline(doc: str) -> str:
        """replace '\\n' -> '<br>'"""
        return doc.replace("\n", "<br>")

    def document_body(docs: Optional[str]) -> str:
        """build documentation body"""
        return (
            "<p>%s</p>" % escape_newline(escape_space(escape(docs, quote=False)))
            if docs
            else ""
        )

    def render_html(header: str, docs: str = None) -> str:
        """render docstring to html"""
        return "".join([header, document_body(docs)]) if header else ""

    def build_rpc(help_: BaseName) -> Optional[Dict[str, Any]]:
        """build rpc content"""

        header_template = '<code><a href="">{module}.{name}</a> (<em>{type_}</em>)</code>'.format(
            module=help_.module_name, name=help_.name, type_=help_.type
        )

        return (
            None
            if help_.is_keyword
            else rpc.Documentation.builder(
                html_result=render_html(header_template, help_.docstring()),
                link=rpc.DocumentLink.builder(
                    uri=str(help_.module_path) if help_.module_path else None,
                    position=rpc.Position.builder(
                        line=help_.line, character=help_.column
                    ),
                ),
            )
        )

    def to_rpc(helps: List[BaseName]) -> Optional[Dict[str, Any]]:
        """convert docstring to rpc"""

        return build_rpc(helps[0]) if helps else None

    class Documentation:
        def __init__(
            self, source: str, *, line: int, column: int, project: Project = None
        ):
            script = Script(source, project=project)
            self.candidates = script.help(line, column)

        def to_rpc(self):
            return to_rpc(self.candidates)


except ImportError:
    print("module 'jedi' not installed, code docstring may not available")
