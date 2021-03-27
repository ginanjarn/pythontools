"""hover"""


import logging
from .remote import RequestMessage, ResponseMessage, request


logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)
sh = logging.StreamHandler()
sh.setFormatter(logging.Formatter("%(levelname)s\t%(module)s: %(lineno)d\t%(message)s"))
sh.setLevel(logging.DEBUG)
logger.addHandler(sh)


def fetch_documentation(src: str, line: int, character: int) -> "ResponseMessage":
    """get documentation

    Raises:
        InvalidInput
        InvalidResponse
        ServerOffline
    """

    message = RequestMessage("textDocument.hover")
    message.params = {
        "uri": src,
        "location": {"line": line, "character": character},
    }
    logger.debug(message)
    response = request(message.to_rpc(), timeout=3)
    logger.debug(response)
    return ResponseMessage.from_rpc(response)
