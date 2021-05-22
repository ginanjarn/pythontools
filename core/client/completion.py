"""completion"""


import logging
from .remote import RequestMessage, ResponseMessage, request, generate_id


logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)
sh = logging.StreamHandler()
template = "%(asctime)s - %(levelname)s::%(module)s: %(lineno)d\t%(message)s"
sh.setFormatter(logging.Formatter(template))
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
    response = request(message.to_rpc(), timeout=30)
    logger.debug(response)
    return ResponseMessage.from_rpc(response)
