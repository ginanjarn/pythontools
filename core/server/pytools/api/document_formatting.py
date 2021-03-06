"""document formatting module"""


from typing import Tuple, List, Any, Dict
import difflib
import logging
import re

from api import rpc, errors


logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)
sh = logging.StreamHandler()
template = "%(asctime)s - %(levelname)s::%(module)s: %(lineno)d\t%(message)s"
sh.setFormatter(logging.Formatter(template))
sh.setLevel(logging.DEBUG)
logger.addHandler(sh)


try:
    import black

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

    def to_rpc(results: str, *, source: str) -> Dict[str, Any]:
        return Updates(old=source, new=results).build_rpc()

    def format_with_black(source: str) -> str:
        mode = black.FileMode(
            target_versions=set(),
            is_pyi=False,
            line_length=black.DEFAULT_LINE_LENGTH,
            string_normalization=True,
        )
        try:
            formatted = black.format_file_contents(source, fast=False, mode=mode)
        except black.NothingChanged:
            return source
        return formatted

    class DocumentFormatting:
        def __init__(self, source: str):
            self.source = source
            try:
                self.candidates = format_with_black(source)
            except black.InvalidInput as err:
                raise errors.InvalidInput(str(err)) from None

        def to_rpc(self):
            return to_rpc(self.candidates, source=self.source)


except ImportError:
    print("module 'black' not installed, code formatting may not available")
