"""completion"""


import logging
from .remote import RequestMessage, ResponseMessage, request, generate_id


logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)
sh = logging.StreamHandler()
sh.setFormatter(logging.Formatter("%(levelname)s\t%(module)s: %(lineno)d\t%(message)s"))
sh.setLevel(logging.DEBUG)
logger.addHandler(sh)


def fetch_completion(src: str, line: int, character: int) -> "ResponseMessage":
    """get completion data

    Raises:
        InvalidInput
        InvalidResponse
        ServerOffline
    """

    message = RequestMessage.builder(generate_id(), "textDocument.completion")
    message.params = {
        "uri": src,
        "location": {"line": line, "character": character},
    }
    response = request(message.to_rpc(), timeout=5)
    logger.debug(response)
    return ResponseMessage.from_rpc(response)
