"""service"""


from re import findall
import socket
import logging
import json
from random import random

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
sh = logging.StreamHandler()
sh.setFormatter(logging.Formatter("%(levelname)s\t%(module)s: %(lineno)d\t%(message)s"))
sh.setLevel(logging.DEBUG)
logger.addHandler(sh)


class ContentIncomplete(ValueError):
    """Content incomplete"""


class ContentOverflow(ValueError):
    """Content too large"""


class InvalidResponse(Exception):
    """Invalid response"""


RPC_SEPARATOR = b"\r\n\r\n"


def get_rpc_content(message: bytes) -> str:
    """get rpc content"""
    header, content = message.split(RPC_SEPARATOR)

    def get_content_length(header: bytes) -> int:
        """get content length"""
        decoded = header.decode("ascii")
        found = findall(r"Content-Length: (\d*)\s?", decoded)
        if not any(found):
            raise ValueError("unable fetch content length from '%s'" % decoded)
        return int(found[0])

    required_len = get_content_length(header)
    if len(content) < required_len:
        raise ContentIncomplete
    if len(content) > required_len:
        raise ContentOverflow
    return content.decode("utf-8")


def create_rpc_message(message: str) -> bytes:
    """create rpc message"""
    content_encoded = message.encode("utf-8")
    header = "Content-Length: %s" % (len(content_encoded))
    return b"%s%s%s" % (header.encode("ascii"), RPC_SEPARATOR, content_encoded)


class RequestMessage:
    """Request message helper"""

    def __init__(self, method: str, params: "Optional[Any]" = None) -> None:
        self.id = str(random())
        self.method = method
        self.params = params

    def to_rpc(self) -> str:
        """convert to rpc message"""
        message = {"id": self.id, "method": self.method, "params": self.params}
        return json.dumps(message)


class Service:
    """client service handler"""

    @staticmethod
    def request(message: str, host: str = "127.0.0.1", port: int = 8088) -> str:
        """handle socket request

        Raises:
            ConnectionError
            InvalidResponse
            """
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as conn:
            conn.connect((host, port))
            conn.sendall(create_rpc_message(message))

            result = ""
            recv = b""
            while True:
                data = conn.recv(1024)
                try:
                    recv += data
                    content = get_rpc_content(recv)
                except ContentIncomplete:
                    continue
                except ContentOverflow:
                    logger.error("content overflow")
                    raise InvalidResponse from None
                else:
                    logger.debug(content)
                    result = content
                    break

        logger.debug(result)
        return result
