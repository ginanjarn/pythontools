"""analyzer"""


import logging
from .remote import RequestMessage, ResponseMessage, request_task


logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)
sh = logging.StreamHandler()
sh.setFormatter(logging.Formatter("%(levelname)s\t%(module)s: %(lineno)d\t%(message)s"))
sh.setLevel(logging.DEBUG)
logger.addHandler(sh)


def get_diagnostic(path: str) -> "ResponseMessage":
    """get diagnostic data"""

    message = RequestMessage("textDocument.get_diagnostic")
    message.params = {
        "uri": path,
    }
    logger.debug(message)
    response = request_task(message.to_rpc())
    logger.debug(response)
    response_message = ResponseMessage.from_rpc(response)
    return response_message
