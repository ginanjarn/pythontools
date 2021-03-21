"""document operation"""


import os
import sublime  # pylint: disable=import-error
import logging

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)
sh = logging.StreamHandler()
sh.setFormatter(logging.Formatter("%(levelname)s\t%(module)s: %(lineno)d\t%(message)s"))
sh.setLevel(logging.DEBUG)
logger.addHandler(sh)


def show_completions(view: "sublime.View") -> None:
    """Opens (forced) the sublime autocomplete window"""

    view.run_command("hide_auto_complete")
    view.run_command(
        "auto_complete",
        {
            "disable_auto_insert": True,
            "next_completion_if_showing": False,
            "auto_complete_commit_on_tab": True,
        },
    )


def show_popup(
    view: "sublime.View", content: str, location: int, callback: "Callable[[str],None]"
) -> None:
    """Open popup"""

    view.show_popup(
        content,
        sublime.HIDE_ON_MOUSE_MOVE_AWAY | sublime.COOPERATE_WITH_AUTO_COMPLETE,
        location=location,
        max_width=1024,
        on_navigate=callback,
    )


def open_link(view: "sublime.View", link: str) -> None:
    """open link"""

    if not link:
        return None

    view_path = os.path.abspath(view.file_name())
    path = "{mod_path}:{line}:{character}".format(
        mod_path=view_path if link["path"] is None else link["path"],
        line=0 if link["line"] is None else link["line"],
        character=0 if link["character"] is None else link["character"] + 1,
    )
    return view.window().open_file(path, sublime.ENCODED_POSITION)


class Update:
    """Update helper class"""

    __slots__ = ["_pos_changes", "region", "new_text"]

    def __init__(self, update_region: sublime.Region, value: str) -> None:
        self._pos_changes = len(value) - update_region.size()
        self.region = update_region
        self.new_text = value

    @property
    def pos_changes(self) -> int:
        return self._pos_changes

    def adjust_position(self, changes: int) -> None:
        self.region.a += changes
        self.region.b += changes

    def __repr__(self) -> str:
        return "region: {region}, pos changes: {pos_changes}, new text: {new_text}".format(
            region=self.region, pos_changes=self._pos_changes, new_text=self.new_text
        )

    @classmethod
    def from_rpc(cls, view: sublime.View, update: "Dict[str, Any]") -> "Update":
        """load from rpc"""

        start_line = update["range"]["start"]["line"]
        start_column = update["range"]["start"]["character"]
        end_line = update["range"]["end"]["line"]
        end_column = update["range"]["end"]["character"]
        new_text = update["newText"]

        logger.debug("%s, %s, %s, %s", start_line, start_column, end_line, end_column)
        start = view.text_point(start_line - 1, start_column)
        end = view.text_point(end_line - 1, end_column)
        region = sublime.Region(start, end)
        return cls(region, new_text)


def apply_changes(
    view: sublime.View, edit: sublime.Edit, changes: "List[str, Any]"
) -> None:
    """apply changes to active view

    Argumens
        changes: str
            rpc message
            Ex: [{"range": {"start": {"line":0, "character":0},
                "end": {"line": 0, "character": 0}}, "newText": ""}]
    """
    # type : Callable[sublime.View, sublime.Edit, Any] -> None

    if not changes:
        return  # cancel if empty

    pos_changes = 0
    new_values = []  # type : List[Update]

    for change in changes:
        update = Update.from_rpc(view, change)
        logger.debug(str(update))
        new_values.append(update)

    # separated to prevent view content changes
    for value in new_values:
        value.adjust_position(pos_changes)
        region = value.region
        view.erase(edit, region)
        view.insert(edit, region.a, value.new_text)
        pos_changes += value.pos_changes


def show_input_panel(
    window: sublime.Window,
    caption: str,
    *,
    initial_text: str = "",
    on_done: "Callback[[str], None]" = None
) -> None:
    window.show_input_panel(
        caption=caption,
        initial_text=initial_text,
        on_done=on_done,
        on_change=None,
        on_cancel=None,
    )


# Severity
ERROR = 1
WARNING = 2
INFO = 3
HINT = 4


class Mark:
    """diagnostic mark item"""

    def __init__(self, severity, region, message):
        self.severity = severity
        self.region = region
        self.message = message

    def __repr__(self):
        return "severity : {severity}, region : {region}, message : {message}".format(
            severity=self.severity, region=self.region, message=self.message
        )

    @classmethod
    def from_rpc(cls, view, message):
        try:
            pos = view.text_point(message["line"] - 1, message["column"])
            region = view.line(pos) if message["column"] == 0 else view.word(pos)
            severity = message["severity"]
            msg = "%s: %s" % (message["code"], message["message"])
        except KeyError:
            return None
        else:
            return cls(severity, region, msg)


SCOPE = {1: "Invalid", 2: "Invalid", 3: "Comment", 4: "Comment"}

ICON_PREFIX = "Packages/pythontools/icons/%s"
ICON = {
    1: ICON_PREFIX % "error.png",
    2: ICON_PREFIX % "warning.png",
    3: ICON_PREFIX % "info.png",
    4: ICON_PREFIX % "info.png",
}

FLAGS = {
    1: sublime.DRAW_NO_OUTLINE,
    2: sublime.DRAW_NO_FILL | sublime.DRAW_NO_OUTLINE | sublime.DRAW_SOLID_UNDERLINE,
    3: sublime.DRAW_NO_FILL
    | sublime.DRAW_NO_OUTLINE
    | sublime.DRAW_SOLID_UNDERLINE
    | sublime.HIDE_ON_MINIMAP,
    4: sublime.DRAW_NO_FILL
    | sublime.DRAW_NO_OUTLINE
    | sublime.DRAW_SQUIGGLY_UNDERLINE
    | sublime.HIDE_ON_MINIMAP,
}

KEY_FORMAT = "pytools:%s"


def add_regions(view: sublime.View, key, regions, scope, icon, flags):
    view.add_regions(
        key=key, regions=list(regions), scope=scope, icon=icon, flags=flags
    )


def erase_regions(view: sublime.View, key):
    view.erase_regions(key)


def apply_diagnostics(
    view: sublime.View, marks: "Iterable[Mark]",
):

    for severity in [HINT, INFO, WARNING, ERROR]:
        filtered_mark = filter(lambda mark: mark.severity == severity, marks)
        # logger.debug(list(filtered_mark))
        regions = map(lambda mark: mark.region, filtered_mark)
        # logger.debug(list(regions))

        key = KEY_FORMAT % (severity)
        erase_regions(view, key)
        add_regions(
            view, key, regions, SCOPE[severity], ICON[severity], FLAGS[severity]
        )


def diagnostic_message(diagnostics: "List[Mark]", view: sublime.View, pos: int):
    def intersecting(mark: Mark):
        line = view.line(pos)
        # line: sublime.Region = line
        return line.intersects(mark.region)

    intersects = filter(intersecting, diagnostics)
    messages = map(lambda mark: mark.message, intersects)
    return "<br>".join(messages)
