"""rename"""


import logging
from .remote import RequestMessage, ResponseMessage, request


logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)
sh = logging.StreamHandler()
sh.setFormatter(logging.Formatter("%(levelname)s\t%(module)s: %(lineno)d\t%(message)s"))
sh.setLevel(logging.DEBUG)
logger.addHandler(sh)


def rename(file_path: str, offset: int, new_name: str) -> "ResponseMessage":
    """rename any object
    
    Arguments:
        file_path : str
        offset : str
            offset location to attribute, -1 to rename module
        new_name : str

    Raises:
        InvalidInput
        InvalidResponse
        ServerOffline
    """

    message = RequestMessage("document.rename")
    message.params = {
        "uri": file_path,
        "location": offset,
        "new_name": new_name,
    }
    response = request(message.to_rpc())
    logger.debug(response)
    return ResponseMessage.from_rpc(response)
