"""document operation"""


import sublime  # pylint: disable=import-error
import logging

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)
sh = logging.StreamHandler()
template = "%(asctime)s - %(levelname)s::%(module)s: %(lineno)d\t%(message)s"
sh.setFormatter(logging.Formatter(template))
sh.setLevel(logging.DEBUG)
logger.addHandler(sh)


def show_completions(view: sublime.View) -> None:
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
    view: sublime.View,
    content: str,
    location: int,
    callback: "Callable[[str],None]",
    update: bool = False,
) -> None:
    """Open popup"""

    if update and view.is_popup_visible():
        # update active popup content
        view.update_popup(content)

    else:
        view.show_popup(
            content,
            sublime.HIDE_ON_MOUSE_MOVE_AWAY | sublime.COOPERATE_WITH_AUTO_COMPLETE,
            location=location,
            max_width=1024,
            on_navigate=callback,
        )


def open_link(view: sublime.View, link: "Dict[str,Any]") -> None:
    """open link

    Params:
        view: sublime.View)
            active view
        
        link: Dict[str,Any])
            link contain {"uri":path_to_file,"line":line_pos,"character":column_pos}
    """

    if not link:
        return None

    path = "{mod_path}:{line}:{character}".format(
        mod_path=view.file_name() if link["uri"] is None else link["uri"],
        line=0 if link["location"]["line"] is None else link["location"]["line"],
        character=0
        if link["location"]["character"] is None
        else link["location"]["character"] + 1,
    )
    return view.window().open_file(path, sublime.ENCODED_POSITION)


class Update:
    """Update helper class"""

    __slots__ = ["_position_changes", "region", "new_text"]

    def __init__(self, update_region: sublime.Region, text: str) -> None:
        self._position_changes = len(text) - update_region.size()
        self.region = update_region
        self.new_text = text

    @property
    def pos_changes(self) -> int:
        return self._position_changes

    def adjust_position(self, changes: int) -> None:
        self.region.a += changes
        self.region.b += changes

    def __repr__(self) -> str:
        return "region: {region}, pos changes: {pos_changes}, new text: {new_text}".format(
            region=self.region,
            pos_changes=self._position_changes,
            new_text=self.new_text,
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
        start = view.text_point(start_line, start_column)
        end = view.text_point(end_line, end_column)
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

    if not changes:
        return  # cancel if empty

    def generate_updates(changes: "Dict[str: Any]") -> "Iterable[Update]":
        for change in changes:
            update = Update.from_rpc(view, change)
            logger.debug(str(update))
            yield update

    updates = list(generate_updates(changes))  # type: List[Update]
    pos_changes = 0

    for update in updates:
        update.adjust_position(pos_changes)
        region = update.region
        view.erase(edit, region)
        view.insert(edit, region.a, update.new_text)
        pos_changes += update.pos_changes


def show_input_panel(
    window: sublime.Window,
    caption: str,
    *,
    initial_text: str = "",
    on_done: "Callable[[str], None]" = None,
    on_change: "Callable[[str], None]" = None,
    on_cancel: "Callable[[str], None]" = None
) -> None:

    window.show_input_panel(
        caption=caption,
        initial_text=initial_text,
        on_done=on_done,
        on_change=on_change,
        on_cancel=on_cancel,
    )


# Severity
ERROR = 1
WARNING = 2
INFO = 3
HINT = 4


class Mark:
    """diagnostic mark item"""

    def __init__(
        self, view_id: int, severity: int, region: sublime.Region, message: str
    ):
        self.view_id = view_id
        self.severity = severity
        self.region = region
        self.message = message

    def __repr__(self):
        return "view_id : {view_id}, severity : {severity}, region : {region}, message : {message}".format(
            view_id=self.view_id,
            severity=self.severity,
            region=self.region,
            message=self.message,
        )

    @classmethod
    def from_rpc(cls, view: sublime.View, message: str) -> "Mark":
        try:
            pos = view.text_point(message["line"] - 1, message["column"])
            region = view.line(pos) if message["column"] == 0 else view.word(pos)
            severity = message["severity"]
            msg = "%s: %s" % (message["code"], message["message"])
        except KeyError:
            return None
        else:
            return cls(view.id(), severity, region, msg)


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


def add_regions(
    view: sublime.View,
    key: str,
    regions: "Iterable[sublime.Region]",
    scope: str,
    icon: str,
    flags: "Any",
):
    view.add_regions(
        key=key, regions=list(regions), scope=scope, icon=icon, flags=flags
    )


def erase_regions(view: sublime.View, key: str):
    view.erase_regions(key)


def mark_document(
    view: sublime.View, marks: "Iterable[Mark]",
):
    # marks in current view
    current_view_mark = [mark for mark in marks if mark.view_id == view.id()]

    for severity in [ERROR, WARNING, INFO, HINT]:
        severity_filtered_mark = (
            mark for mark in current_view_mark if mark.severity == severity
        )

        # get region on mark
        regions = (mark.region for mark in severity_filtered_mark)
        key = KEY_FORMAT % (severity)

        erase_regions(view, key)
        add_regions(
            view, key, regions, SCOPE[severity], ICON[severity], FLAGS[severity]
        )


def diagnostic_message(
    diagnostics: "List[Mark]", view: sublime.View
) -> "Dict[int, str]":
    """get line mapped diagnostic message in current view"""

    message_map = {}

    for mark in diagnostics:

        row, _ = view.rowcol(mark.region.a)
        message = mark.message

        if row in message_map:
            message_map[row] = "<br>".join([message_map[row], message])
        else:
            message_map[row] = message

    return message_map


class OutputPanel:
    """Output panel handler"""

    def __init__(self, window: sublime.Window, name: str):
        self.panel_name = name
        self.window = window
        self.panel = window.get_output_panel(self.panel_name)
        if not self.panel:
            self.panel = window.create_output_panel(self.panel_name)
            self.panel.set_read_only(False)
        else:
            self.clear()

    def append(self, *args):
        """append message to panel"""

        for message in args:
            self.panel.run_command(
                "append", {"characters": message + "\n"},
            )

    def clear(self):
        """clear panel message"""
        self.panel.run_command("clear")

    def show(self):
        """show panel"""
        self.window.run_command("show_panel", {"panel": "output.%s" % self.panel_name})

    def hide(self):
        """hide panel"""
        self.window.run_command("hide_panel", {"panel": "output.%s" % self.panel_name})

    def destroy(self):
        """destroy panel"""
        self.window.destroy_output_panel(self.panel_name)
