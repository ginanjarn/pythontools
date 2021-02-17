"""hover"""


import logging
from .remote import RequestMessage, ResponseMessage, request_task


logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)
sh = logging.StreamHandler()
sh.setFormatter(logging.Formatter("%(levelname)s\t%(module)s: %(lineno)d\t%(message)s"))
sh.setLevel(logging.DEBUG)
logger.addHandler(sh)


def fetch_documentation(src: str, line: str, character: str) -> "ResponseMessage":
    """get sublime formatted documentation data"""

    message = RequestMessage("textDocument.hover")
    message.params = {
        "uri": src,
        "location": {"line": line, "character": character},
    }
    logger.debug(message)
    response = request_task(message.to_rpc())
    logger.debug(response)
    response_message = ResponseMessage.from_rpc(response)
    return response_message
