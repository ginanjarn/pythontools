"""document format"""


import logging
from .remote import RequestMessage, ResponseMessage, request_task


logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)
sh = logging.StreamHandler()
sh.setFormatter(logging.Formatter("%(levelname)s\t%(module)s: %(lineno)d\t%(message)s"))
sh.setLevel(logging.DEBUG)
logger.addHandler(sh)


def format_code(src: str) -> "ResponseMessage":
    """get sublime formatted PEP formatted data"""

    message = RequestMessage("textDocument.formatting")
    message.params = {"uri": src}
    response = request_task(message.to_rpc())
    logger.debug(response)
    response_message = ResponseMessage.from_rpc(response)
    return response_message
