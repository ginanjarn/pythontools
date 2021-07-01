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


def hide_completions(view: sublime.View) -> None:
    """Opens (forced) the sublime autocomplete window"""

    view.run_command("hide_auto_complete")


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


class DocumentLink:
    def __init__(self, path: str, line: int, column: int):
        self.path = path
        self.line = line
        self.column = column

    @property
    def path_encoded(self):
        return "{path}:{line}:{column}".format(
            path=self.path, line=self.line, column=self.column,
        )

    @classmethod
    def from_rpc(cls, view: sublime.View, params: "Dict[str, Any]"):

        if not params:
            raise ValueError("params empty")

        path = view.file_name() if params["uri"] is None else params["uri"]
        line = 0 if params["location"]["line"] is None else params["location"]["line"]
        column = (
            0
            if params["location"]["character"] is None
            else params["location"]["character"] + 1
        )
        return cls(path, line, column)


def open_link(view: sublime.View, link: DocumentLink) -> None:
    """open link"""
    if not link:
        return

    return view.window().open_file(link.path_encoded, sublime.ENCODED_POSITION)


class ChangeItem:
    """ChangeItem hold change data"""

    __slots__ = [
        "position_change",
        "region",
        "new_text",
    ]

    def __init__(self, update_region: sublime.Region, text: str):
        self.position_change = len(text) - update_region.size()
        self.region = update_region
        self.new_text = text

    def get_region(self, pos_change: int = 0) -> sublime.Region:
        self.region.a += pos_change
        self.region.b += pos_change
        return self.region

    def __repr__(self) -> str:
        return "region: {region}, pos changes: {pos_changes}, new text: {new_text}".format(
            region=self.region,
            pos_changes=self.position_change,
            new_text=self.new_text,
        )

    @classmethod
    def from_rpc(cls, view: sublime.View, params: "Dict[str, Any]"):
        """load from rpc"""

        start_line = params["range"]["start"]["line"]
        start_column = params["range"]["start"]["character"]
        end_line = params["range"]["end"]["line"]
        end_column = params["range"]["end"]["character"]
        new_text = params["newText"]

        logger.debug("%s, %s, %s, %s", start_line, start_column, end_line, end_column)
        start = view.text_point(start_line, start_column)
        end = view.text_point(end_line, end_column)
        region = sublime.Region(start, end)
        return cls(region, new_text)


class DocumentChange:
    """DocumentChange handle documnet change"""

    def __init__(
        self, view: sublime.View, edit: sublime.Edit, changes: "List[ChangeItem]"
    ):
        self.view = view
        self.edit = edit
        self.changes = changes

    def apply_changes(self):
        """apply change to active edit"""

        view = self.view
        edit = self.edit
        position_change = 0

        for change in self.changes:
            # change: ChangeItem = change

            region = change.get_region(position_change)
            view.erase(edit, region)
            view.insert(edit, region.a, change.new_text)
            position_change += change.position_change

    @classmethod
    def from_rpc(cls, view: sublime.View, edit: sublime.Edit, params: "Dict[str, Any]"):
        changes = [ChangeItem.from_rpc(view, change) for change in params]
        return cls(view, edit, changes)


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


class MarkItem:
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
    def from_rpc(cls, view: sublime.View, message: str) -> "MarkItem":
        try:
            pos = view.text_point(message["line"] - 1, message["column"])
            region = view.line(pos) if message["column"] == 0 else view.word(pos)
            severity = message["severity"]
            msg = "%s: %s" % (message["code"], message["message"])
        except KeyError:
            return None
        else:
            return cls(view.id(), severity, region, msg)


class Diagnostics:
    """Diagnostics handle diagnostic message and mark on view"""

    def __init__(self, view: sublime.View, marks: "Iterable[MarkItem]"):
        self.view = view
        self.marks = [mark for mark in marks if mark.view_id == view.id()]

    @staticmethod
    def get_scope(severity):
        scope = {1: "Invalid", 2: "Invalid", 3: "Comment", 4: "Comment"}
        return scope[severity]

    @staticmethod
    def get_icon(severity):
        icon = {
            1: "error.png",
            2: "warning.png",
            3: "info.png",
            4: "info.png",
        }
        return "Packages/pythontools/icons/%s" % icon[severity]

    @staticmethod
    def get_flags(severity):
        flags = {
            1: sublime.DRAW_NO_OUTLINE,
            2: sublime.DRAW_NO_FILL
            | sublime.DRAW_NO_OUTLINE
            | sublime.DRAW_SOLID_UNDERLINE,
            3: sublime.DRAW_NO_FILL
            | sublime.DRAW_NO_OUTLINE
            | sublime.DRAW_SOLID_UNDERLINE
            | sublime.HIDE_ON_MINIMAP,
            4: sublime.DRAW_NO_FILL
            | sublime.DRAW_NO_OUTLINE
            | sublime.DRAW_SQUIGGLY_UNDERLINE
            | sublime.HIDE_ON_MINIMAP,
        }
        return flags[severity]

    @staticmethod
    def create_region_key(severity):
        return "pytools:%s" % severity

    @staticmethod
    def clean_all_marks(view):
        """clean all marks on view"""

        for severity in (ERROR, WARNING, INFO, HINT):
            key = Diagnostics.create_region_key(severity)
            view.erase_regions(key)

    @staticmethod
    def _get_regions(
        marks: "Iterable[MarkItem]", severity: int
    ) -> "Iterator[sublime.Region]":
        """get region with severity filtered from marks"""

        severity_filtered_marks = (mark for mark in marks if mark.severity == severity)

        for mark in severity_filtered_marks:
            yield mark.region

    def mark_document(self):
        """apply mark to view"""

        view = self.view
        self.clean_all_marks(view)

        for severity in (ERROR, WARNING, INFO, HINT):

            key = self.create_region_key(severity)
            regions = self._get_regions(self.marks, severity)

            view.add_regions(
                key=key,
                regions=list(regions),
                scope=self.get_scope(severity),
                icon=self.get_icon(severity),
                flags=self.get_flags(severity),
            )

    def get_message_map(self) -> "Dict[int, str]":
        """get line mapped diagnostic message in current view"""

        view = self.view
        message_map = {}

        for mark in self.marks:

            row, _ = view.rowcol(mark.region.a)
            message = mark.message

            if row in message_map:
                message_map[row] = "<br>".join([message_map[row], message])
            else:
                message_map[row] = message

        return message_map


class OutputPanel:
    """Output panel handler"""

    def __init__(self, window: sublime.Window, name: str, reset_message=True):
        self.panel_name = name
        self.window = window
        self.panel = window.get_output_panel(self.panel_name)
        if not self.panel:
            self.panel = window.create_output_panel(self.panel_name)
            self.panel.set_read_only(False)

        if reset_message:
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
