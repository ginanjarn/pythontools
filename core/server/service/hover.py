"""Hover module"""


from html import escape
from jedi import Script, Project
import logging

logger = logging.getLogger("formatting")
# logger.setLevel(logging.DEBUG)
sh = logging.StreamHandler()
sh.setFormatter(logging.Formatter("%(levelname)s\t%(module)s: %(lineno)d\t%(message)s"))
sh.setLevel(logging.DEBUG)
logger.addHandler(sh)


def get_project(path: str) -> "Project":
    """get project property"""
    return Project(path)


def escape_space(doc: str):
    """replace 'double space' -> '&nbsp;'"""
    return doc.replace("  ", "&nbsp;&nbsp;")


def escape_newline(doc: str):
    """replace '\\n' -> '<br>'"""
    return doc.replace("\n", "<br>")


def document_body(docs):
    """build documentation body"""
    return (
        "<p>%s</p>" % escape_newline(escape_space(escape(docs, quote=False)))
        if docs
        else ""
    )


def render_html(header: str, docs: str = None) -> str:
    """render docstring to html"""
    return "".join([header, document_body(docs)]) if header else ""


def to_rpc(helps: "List[Name]") -> "Dict[str, Any]":
    """convert docstring to rpc"""

    def build_rpc(help_):

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

    return build_rpc(helps[0]) if any(helps) else None


def get_documentation(source: str, line: int, column: int, **kwargs) -> "Any":
    """complete script at following pos(line, column)"""

    project = kwargs.get("project", None)
    path = kwargs.get("path", "")
    # logger.debug(project)
    script = Script(code=source, path=path, project=project)
    results = script.help(line=line, column=column)
    raw = kwargs.get("raw", None)
    return to_rpc(results) if not raw else results
