"""document format"""


import logging
from .remote import RequestMessage, ResponseMessage, request


logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)
sh = logging.StreamHandler()
template = "%(asctime)s - %(levelname)s::%(module)s: %(lineno)d\t%(message)s"
sh.setFormatter(logging.Formatter(template))
sh.setLevel(logging.DEBUG)
logger.addHandler(sh)


def format_code(src: str) -> "ResponseMessage":
    """prettify code

    Raises:
        InvalidInput
        InvalidResponse
        ServerOffline
    """

    message = RequestMessage.builder("textDocument.formatting")
    message.params = {"uri": src}
    response = request(message.to_rpc(), timeout=30)
    logger.debug(response)
    return ResponseMessage.from_rpc(response)
