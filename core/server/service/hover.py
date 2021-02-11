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


def render_html(header: str, docs: str = None) -> str:
    """render docstring to html"""

    if not header:
        return ""

    def escape_space(doc: str):
        """replace 'space' -> '&nbsp;'"""
        return doc.replace("  ", "&nbsp;&nbsp;")

    def escape_newline(doc: str):
        """replace '\\n' -> '<br>'"""
        return doc.replace("\n", "<br>")

    def document_body(docs):
        """build documentation body"""
        if not docs:
            return ""
        return "<p>%s</p>" % escape_newline(escape_space(escape(docs, quote=False)))

    return "".join([header, document_body(docs)])


def to_rpc(helps: "List[Name]") -> "Dict[str, Any]":
    """convert docstring to rpc"""

    def make_rpc(helps):
        help_ = helps[0]

        header_template = '<code><a href="">{module}.{name}</a> [<em>{type_}</em>]</code>'.format(
            module=help_.module_name, name=help_.name, type_=help_.type
        )

        if help_.is_keyword:
            return None

        return {
            "html": render_html(header_template, help_.docstring()),
            "link": {
                "path": help_.module_path,
                "line": help_.line,
                "character": help_.column,
            },
        }

    return make_rpc(helps) if any(helps) else None


def get_documentation(source: str, line: int, column: int, **kwargs) -> "Any":
    """complete script at following pos(line, column)"""
    project = kwargs.get("project", None)
    path = kwargs.get("path", "")
    # logger.debug(project)
    script = Script(code=source, path=path, project=project)
    results = script.help(line=line, column=column)
    raw = kwargs.get("raw", None)
    return to_rpc(results) if not raw else results
