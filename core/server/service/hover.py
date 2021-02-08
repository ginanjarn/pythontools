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
        return

    def wrap_paragraph(doc: str):
        """wrap paragraph with 'p' tag"""
        return "".join(["<p>%s</p>" % par for par in doc.split("\n\n")])

    def wrap_line(doc: str):
        """wrap line with 'br' tag"""
        return "<br>".join(doc.split("\n"))

    body = ""
    if docs:
        escaped = escape(docs, quote=False)
        pwrapped = wrap_paragraph(escaped)
        lnwrapped = wrap_line(pwrapped)
        body = lnwrapped
    return header + body


def to_rpc(helps: "List[Name]") -> "Dict[str, Any]":
    """convert docstring to rpc"""

    def make_rpc(helps):
        help_ = helps[0]

        header_template = '<code>{type}: <a href="">{name}</a></code>'.format(
            type=help_.type, name=help_.name
        )

        if help_.is_keyword:
            html_ = render_html(header_template)
        else:
            html_ = render_html(header_template, help_.docstring())
        return {
            "html": html_,
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
    logger.debug(project)
    script = Script(code=source, path=path, project=project)
    results = script.help(line=line, column=column)
    raw = kwargs.get("raw", None)
    return to_rpc(results) if not raw else results
