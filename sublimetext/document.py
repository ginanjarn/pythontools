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


def show_completions(view):
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


def show_popup(view, content, location, callback):
    """Open popup"""

    view.show_popup(
        content,
        sublime.HIDE_ON_MOUSE_MOVE_AWAY | sublime.COOPERATE_WITH_AUTO_COMPLETE,
        location=location,
        max_width=1024,
        on_navigate=callback,
    )


def open_link(view, link):
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

    def __init__(self, update_region: sublime.Region, value: str):
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
    def from_rpc(cls, view, update):
        # type: Callable[sublime.View, Dict[str, Any]] -> "Update"

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


def apply_changes(view: sublime.View, edit: sublime.Edit, changes):
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
