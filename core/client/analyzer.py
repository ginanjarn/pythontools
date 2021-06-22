"""analyzer"""


import logging
from .remote import RequestMessage, ResponseMessage, request


logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)
sh = logging.StreamHandler()
template = "%(asctime)s - %(levelname)s::%(module)s: %(lineno)d\t%(message)s"
sh.setFormatter(logging.Formatter(template))
sh.setLevel(logging.DEBUG)
logger.addHandler(sh)


def get_diagnostic(path: str) -> "ResponseMessage":
    """get diagnostic data

    Raises:
        InvalidInput
        InvalidResponse
        ServerOffline
    """

    message = RequestMessage.builder("textDocument.get_diagnostic")
    message.params = {
        "uri": path,
    }
    logger.debug(message)
    response = request(message.to_rpc(), timeout=180)
    logger.debug(response)
    return ResponseMessage.from_rpc(response)


def validate(path: str) -> "ResponseMessage":
    """get diagnostic data

    Raises:
        InvalidInput
        InvalidResponse
        ServerOffline
    """

    message = RequestMessage.builder("textDocument.validate")
    message.params = {
        "uri": path,
    }
    logger.debug(message)
    response = request(message.to_rpc(), timeout=180)
    logger.debug(response)
    return ResponseMessage.from_rpc(response)
