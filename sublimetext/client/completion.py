"""completion"""


import logging
from .remote import RequestMessage, ResponseMessage, request_task


logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)
sh = logging.StreamHandler()
sh.setFormatter(logging.Formatter("%(levelname)s\t%(module)s: %(lineno)d\t%(message)s"))
sh.setLevel(logging.DEBUG)
logger.addHandler(sh)


def fetch_completion(src: str, line: str, character: str) -> "ResponseMessage":
    """get completion data"""

    message = RequestMessage("textDocument.completion")
    message.params = {
        "uri": src,
        "location": {"line": line, "character": character},
    }
    response = request_task(message.to_rpc())
    logger.debug(response)
    response_message = ResponseMessage.from_rpc(response)
    return response_message
