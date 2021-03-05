"""document rename module"""

from typing import Text, Tuple, List, Iterator, Any, Union, Dict, Optional
import os
import re
import difflib

from rope.base import project, libutils
from rope.base.change import ChangeSet, MoveResource, ChangeContents
from rope.refactor import rename
from rope.refactor.rename import Rename
from contextlib import contextmanager
import logging

logger = logging.getLogger("rename")
# logger.setLevel(logging.DEBUG)
sh = logging.StreamHandler()
sh.setFormatter(logging.Formatter("%(levelname)s\t%(module)s: %(lineno)d\t%(message)s"))
sh.setLevel(logging.DEBUG)
logger.addHandler(sh)


def get_removed(line: str) -> Tuple[int, int]:
    """get diff removed line"""

    found = re.findall(r"@@ \-(\d*),?(\d*)\s.*@@", line)
    if not any(found):
        raise ValueError("unable to parse diff header", line)
    start_str = found[0][0]
    span_str = found[0][1]
    start = int(start_str)
    span = int(span_str) - 1 if span_str else 0
    end = start + span
    return start, end


class TextEdit:
    def __init__(self, change_diff, old_source):
        self.change_diff = change_diff
        self.old_source = old_source

    def change_gen(self,) -> Iterator[Union[Dict[str, Any], str]]:
        olds = self.old_source.split("\n")
        logger.debug(olds)
        for line in self.change_diff.split("\n"):
            if line.startswith("@@"):
                start_line, end_line = get_removed(line)
                logger.debug(line)
                change = {
                    "range": {
                        "start": {"line": start_line, "character": 0},
                        "end": {"line": end_line, "character": len(olds[end_line - 1])},
                    }
                }
                logger.debug(change)
                yield change
            elif line.startswith("-"):
                continue
            elif line.startswith("+"):
                logger.debug(line)
                yield line[1:]
            elif line.startswith(" "):
                logger.debug(line)
                yield line[1:]
            else:
                continue

    def to_rpc(self):
        """convert changes to rpc"""

        changes = []
        index = -1
        for change in self.change_gen():
            if isinstance(change, dict):
                changes.append(change)
                index += 1
            else:
                if not changes:  # for list
                    continue
                new_text = changes[index].get("newText")
                if new_text is None:
                    changes[index]["newText"] = change
                else:
                    changes[index]["newText"] = "\n".join([new_text, change])

        logger.debug(changes)
        return changes


class DocumentChanges:
    def __init__(self, file_name, *, old, new):
        self.file_name = file_name
        self.old_source: str = old
        self.new_source: str = new

    def to_rpc(self):
        diff_change = "".join(
            difflib.unified_diff(
                self.old_source.splitlines(keepends=True),
                self.new_source.splitlines(keepends=True),
            )
        )
        logger.debug("diff = \n%s", diff_change)
        changes = TextEdit(change_diff=diff_change, old_source=self.old_source).to_rpc()
        return {
            "type": "change",
            "file_name": self.file_name,
            "changes": changes,
        }


class DocumentRename:
    def __init__(self, old_name, new_name):
        self.old_name = old_name
        self.new_name = new_name

    def to_rpc(self):
        return {
            "type": "rename",
            "changes": {"old_name": self.old_name, "new_name": self.new_name,},
        }


def to_rpc(change_set: ChangeSet):
    for change in change_set.changes:
        if isinstance(change, MoveResource):
            change: MoveResource = change
            yield DocumentRename(
                old_name=change.resource.path, new_name=change.new_resource.path
            ).to_rpc()

        elif isinstance(change, ChangeContents):
            change: ChangeContents = change
            diff_change = change.get_description()
            file_name = change.resource.path
            old_src = change.resource.read()
            yield DocumentChanges(
                file_name, old=old_src, new=change.new_contents
            ).to_rpc()


def rename_attribute(
    project_path: str, resource_path: str, offset: Optional[int], new_name: str
):
    project_manager = project.Project(project_path)
    file_resource = libutils.path_to_resource(project_manager, resource_path)

    rename_task = Rename(project_manager, file_resource, offset)
    changes = rename_task.get_changes(new_name)

    project_manager.close()
    return changes
