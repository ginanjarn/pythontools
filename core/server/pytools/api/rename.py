"""document rename module"""


from typing import Text, Tuple, List, Iterator, Any, Union, Dict, Optional
import os
import re
import difflib
import logging


logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)
sh = logging.StreamHandler()
template = "%(asctime)s - %(levelname)s::%(module)s: %(lineno)d\t%(message)s"
sh.setFormatter(logging.Formatter(template))
sh.setLevel(logging.DEBUG)
logger.addHandler(sh)


try:
    from rope.base import project, libutils
    from rope.base.change import ChangeSet, MoveResource, ChangeContents
    from rope.base.exceptions import RefactoringError
    from rope.refactor.rename import Rename

    class RenameChanges(ChangeSet):
        """rename changes object"""

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
        """TextEdit object"""

        def __init__(self, old: str, new: str) -> None:
            self.old_sources = old.split("\n")
            self.new_sources = new.split("\n")

            self.blocks = []
            self.block_index = -1

            self.build_diff()

        def new_block(self, start_line: int, end_line: int) -> None:
            """create new change block"""

            logger.info("new_block from line %s to %s", start_line, end_line)
            start_character = 0
            end_character = len(self.old_sources[end_line - 1])

            self.block_index += 1
            self.blocks.append(
                {
                    "range": {
                        "start": {"line": start_line - 1, "character": start_character},
                        "end": {"line": end_line - 1, "character": end_character},
                    },
                    "newText": [],
                }
            )
            logger.debug("new_block : %s", self.blocks[self.block_index])

        def add_to_block(self, new_text: str) -> None:
            """add line to change block"""

            logger.debug("add_to_block: %s", new_text)

            if self.block_index < 0:
                raise ValueError("block_index not initialized")

            self.blocks[self.block_index]["newText"].append(new_text)

        def build_diff(self) -> None:
            """build changes diff"""

            logger.info("build_diff")
            for line in difflib.unified_diff(self.old_sources, self.new_sources):
                if line.startswith("@@"):
                    start_line, end_line = get_removed(line)
                    self.new_block(start_line, end_line)

                elif any(
                    [
                        line.startswith("-"),
                        line.startswith("---"),
                        line.startswith("+++"),
                    ]
                ):
                    continue  # pass on removed line

                elif line.startswith("+"):
                    self.add_to_block(line[1:])  # for added line

                else:
                    self.add_to_block(line[1:])  # for unmarked line

            for block in self.blocks:
                block["newText"] = "\n".join(block["newText"])  # list to string

        def to_rpc(self) -> List[Any]:
            """convert to rpc"""

            return self.blocks

    class DocumentChanges:
        """Document changes object"""

        def __init__(self, file_name: str, *, old: str, new: str) -> None:
            self.file_name = file_name
            self.old_source: str = old
            self.new_source: str = new

        def to_rpc(self) -> Dict[str, Any]:
            """convert to rpc"""

            changes = TextEdit(old=self.old_source, new=self.new_source).to_rpc()
            results = {
                "type": "change",
                "file_name": self.file_name,
                "changes": changes,
            }
            logger.debug(results)
            return results

    class DocumentRename:
        """Document rename object"""

        def __init__(self, old_name: str, new_name: str) -> None:
            self.old_name = old_name
            self.new_name = new_name

        def to_rpc(self) -> Dict[str, Any]:
            """convert to rpc"""

            results = {
                "type": "rename",
                "changes": {"old_name": self.old_name, "new_name": self.new_name,},
            }
            logger.debug(results)
            return results

    def rpc_generator(change_set: ChangeSet) -> Iterator[Any]:
        """rpc generator"""

        for change in change_set.changes:
            if isinstance(change, MoveResource):
                change: MoveResource = change
                yield DocumentRename(
                    old_name=change.resource.real_path,
                    new_name=change.new_resource.real_path,
                ).to_rpc()

            elif isinstance(change, ChangeContents):
                change: ChangeContents = change
                diff_change = change.get_description()
                file_name = change.resource.real_path
                old_src = change.resource.read()
                yield DocumentChanges(
                    file_name, old=old_src, new=change.new_contents
                ).to_rpc()

    def to_rpc(change_set: ChangeSet) -> List[Any]:
        """convert to rpc"""

        return list(rpc_generator(change_set))

    def rename_attribute(
        project_path: str, resource_path: str, offset: Optional[int], new_name: str
    ) -> RenameChanges:
        """

        Raises:
            RefactoringError
        """
        try:
            project_manager = project.Project(project_path)
            file_resource = libutils.path_to_resource(project_manager, resource_path)

            rename_task = Rename(project_manager, file_resource, offset)
            changes = rename_task.get_changes(new_name)

            project_manager.close()
            # return RenameChanges(changes)
            return changes

        except RefactoringError as err:
            raise ValueError(err) from err


except ImportError:
    print("module 'rope' not installed, code rename may not available")
