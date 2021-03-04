"""Hover module"""


from html import escape
from jedi import Script, Project
from jedi.api.classes import BaseName
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger("formatting")
# logger.setLevel(logging.DEBUG)
sh = logging.StreamHandler()
sh.setFormatter(logging.Formatter("%(levelname)s\t%(module)s: %(lineno)d\t%(message)s"))
sh.setLevel(logging.DEBUG)
logger.addHandler(sh)


class Documentations(list):
    """documentation list"""


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
        else {
            "html": render_html(header_template, help_.docstring()),
            "link": {
                "path": help_.module_path,
                "line": help_.line,
                "character": help_.column,
            },
        }
    )


def to_rpc(helps: List[BaseName]) -> Optional[Dict[str, Any]]:
    """convert docstring to rpc"""

    return build_rpc(helps[0]) if helps else None


def get_documentation(
    source: str, *, line: int, column: int, project: Project = None
) -> Documentations:
    """complete script at following pos(line, column)

    Raises:
        ValueError: column > len(line_content)
    """

    script = Script(code=source, project=project)
    results = script.help(line=line, column=column)
    return Documentations(results)
