"""document rename module"""


from typing import Tuple, List, Iterator, Any, Dict, Optional
from contextlib import contextmanager
import re
import difflib
import logging
from api import rpc, errors


logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)
sh = logging.StreamHandler()
template = "%(asctime)s - %(levelname)s::%(module)s: %(lineno)d\t%(message)s"
sh.setFormatter(logging.Formatter(template))
sh.setLevel(logging.DEBUG)
logger.addHandler(sh)


try:
    from rope.base import project, libutils
    import rope.base.change as rope_change
    import rope.base.exceptions as rope_exception
    import rope.refactor.rename as rope_rename

    def get_removed(line: str) -> Tuple[int, int]:
        """get diff removed line

        @@ -1,5 +1,10 @@
        =>  remove from line 1 to next 5 lines
            insert from line 1 to next 10 lines
        """

        found = re.findall(r"@@ \-(\d*),?(\d*)\s.*@@", line)
        if not any(found):
            raise ValueError("unable to parse diff header", line)
        start_str = found[0][0]
        span_str = found[0][1]
        start = int(start_str)
        span = int(span_str) - 1 if span_str else 0
        end = start + span
        return start, end

    class Updates:
        """Updates object"""

        def __init__(self, old: str, new: str) -> None:

            self.old_sources = old.split("\n")
            self.new_sources = new.split("\n")

            self.blocks = []
            self.block_index = -1

        def __repr__(self):
            return "\n".join(
                list(difflib.unified_diff(self.old_sources, self.new_sources))
            )

        @staticmethod
        def to_zero_index(n):
            """convert one based diff line index to zero

            difflib use one based line index
            """
            return n - 1

        def new_block(self, start_line: int, end_line: int) -> None:
            """create new change block"""

            logger.info("new_block from line %s to %s", start_line, end_line)
            start_character = 0
            end_character = len(self.old_sources[self.to_zero_index(end_line)])

            self.block_index += 1
            edit = rpc.TextEdit.builder(
                start_line=self.to_zero_index(start_line),
                start_character=start_character,
                end_line=self.to_zero_index(end_line),
                end_character=end_character,
            )
            self.blocks.append(edit)
            logger.debug("new_block : %s", self.blocks[self.block_index])

        def add_to_block(self, new_text: str) -> None:
            """add line to change block"""

            logger.debug("add_to_block: %s", new_text)

            if self.block_index < 0:
                raise ValueError("block_index not initialized")

            self.blocks[self.block_index].accumulate_new_text(new_text)

        def build_diff(self) -> None:
            """build changes diff"""

            logger.info("build_diff")
            for line in difflib.unified_diff(self.old_sources, self.new_sources):

                # ignore this marked line
                if any(
                    [
                        line.startswith("-"),
                        line.startswith("---"),
                        line.startswith("+++"),
                    ]
                ):
                    continue  # pass on removed line

                # create new change group
                if line.startswith("@@"):
                    start_line, end_line = get_removed(line)
                    self.new_block(start_line, end_line)

                # insert updated line
                elif line.startswith("+"):
                    self.add_to_block(line[1:])  # for added line

                # insert unchanges line
                else:
                    self.add_to_block(line[1:])  # for unmarked line

            for block in self.blocks:
                block.build_new_text()

        def build_rpc(self) -> List[Any]:
            """convert to rpc"""

            self.build_diff()
            return self.blocks

    class DocumentChanges:
        """Document changes object"""

        def __init__(self, file_name: str, *, old: str, new: str) -> None:
            self.file_name = file_name
            self.old_source: str = old
            self.new_source: str = new

        def to_rpc(self) -> Dict[str, Any]:
            """convert to rpc"""

            updates = Updates(old=self.old_source, new=self.new_source)
            results = {
                "type": "change",
                "file_name": self.file_name,
                "changes": updates.build_rpc(),
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

    def rpc_generator(change_set: rope_change.ChangeSet) -> Iterator[Any]:
        """rpc generator"""

        for change in change_set.changes:
            if isinstance(change, rope_change.MoveResource):
                change: rope_change.MoveResource = change
                yield DocumentRename(
                    old_name=change.resource.real_path,
                    new_name=change.new_resource.real_path,
                ).to_rpc()

            elif isinstance(change, rope_change.ChangeContents):
                change: rope_change.ChangeContents = change
                file_name = change.resource.real_path
                old_src = change.resource.read()
                yield DocumentChanges(
                    file_name, old=old_src, new=change.new_contents
                ).to_rpc()

    def to_rpc(change_set: rope_change.ChangeSet) -> List[Any]:
        """convert to rpc"""

        return list(rpc_generator(change_set))

    @contextmanager
    def rope_project(project_path: str):
        try:
            project_manager = project.Project(project_path)
            yield project_manager
        finally:
            project_manager.close()

    def rename_attribute(
        project_path: str, resource_path: str, offset: Optional[int], new_name: str
    ) -> Any:
        """

        Raises:
            RefactoringError
        """
        try:
            with rope_project(project_path) as project_manager:
                file_resource = libutils.path_to_resource(
                    project_manager, resource_path
                )
                rename_task = rope_rename.Rename(project_manager, file_resource, offset)
                changes = rename_task.get_changes(new_name)

                return changes

        except rope_exception.RefactoringError as err:
            raise errors.InvalidInput(err) from err

    class Rename:
        def __init__(
            self,
            project_path: str,
            resource_path: str,
            offset: Optional[int],
            new_name: str,
        ):
            self.candidates = rename_attribute(
                project_path, resource_path, offset, new_name
            )

        def to_rpc(self):
            return to_rpc(self.candidates)


except ImportError:
    print("module 'rope' not installed, code rename may not available")
