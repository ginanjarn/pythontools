"""remote handler"""


from re import findall
import os
import socket
import subprocess
import json
from random import random
import threading
import logging

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)
sh = logging.StreamHandler()
sh.setFormatter(logging.Formatter("%(levelname)s\t%(module)s: %(lineno)d\t%(message)s"))
sh.setLevel(logging.DEBUG)
logger.addHandler(sh)


class ContentIncomplete(ValueError):
    """Content incomplete"""


class ContentOverflow(ValueError):
    """Content too large"""


class ContentInvalid(ValueError):
    """Content invalid"""


class InvalidResponse(Exception):
    """Invalid response"""


class ServerError(Exception):
    """Unable to run server"""


class ServerOffline(ConnectionError):
    """Server offline"""


class PortInUse(OSError):
    """Port in use"""


class InvalidInput(TypeError):
    """Input type invalid. Required type `str`"""


RPC_SEPARATOR = b"\r\n\r\n"


def content_length(header: bytes) -> int:
    """get content length"""

    decoded = header.decode("ascii")
    found = findall(r"Content-Length: (\d*)\s?", decoded)
    if not any(found):
        logger.error("unabe parse from %s", header)
        raise ValueError("unable fetch content length from %s" % decoded)
    return int(found[0])


def get_rpc_content(message: bytes) -> str:
    """get rpc content

    Raises:
        ContentInvalid
        ContentIncomplete
        ContentOverflow
    """

    try:
        header, content = message.split(RPC_SEPARATOR)
    except (ValueError, TypeError) as err:
        logger.error("unable parse rpc message from %s", message)
        raise ContentInvalid from err

    if len(content) < content_length(header):
        logger.debug(
            "Length want: %s expected: %s", len(content), content_length(header)
        )
        raise ContentIncomplete(
            "Length: want: %s, expected: %s" % (len(content), content_length(header)),
        )
    if len(content) > content_length(header):
        logger.debug(
            "Length want: %s expected: %s", len(content), content_length(header)
        )
        raise ContentOverflow(
            "Length: want: %s, expected: %s" % (len(content), content_length(header)),
        )
    return content.decode("utf-8")


def create_rpc_message(message: str) -> bytes:
    """create rpc message"""

    content_encoded = message.encode("utf-8")
    logger.debug(content_encoded)
    header = "Content-Length: %s" % (len(content_encoded))
    header_encoded = header.encode("ascii")
    logger.debug(header_encoded)
    encoded = header_encoded + RPC_SEPARATOR + content_encoded
    logger.debug(encoded)
    return encoded


class RequestMessage:
    """Request message helper"""

    def __init__(self, method: str, params: "Optional[Any]" = None) -> None:
        self.req_id = str(random())
        self.method = method
        self.params = params

    def __repr__(self) -> str:
        return "id : {req_id}, method : {method}, params : {params}".format(
            req_id=self.req_id, method=self.method, params=self.params
        )

    def to_rpc(self) -> str:
        """convert to rpc message

        Raises:
            TypeError
        """

        message = {"id": self.req_id, "method": self.method, "params": self.params}
        return json.dumps(message)


class ResponseMessage:
    """Response message helper"""

    def __init__(
        self,
        resp_id: str,
        results: "Optional[Any]" = None,
        error: "Optional[Any]" = None,
    ) -> None:
        self.resp_id = resp_id
        self.results = results
        self.error = error

    def __repr__(self) -> str:
        return "id : {resp_id}, results : {results}, error : {error}".format(
            resp_id=self.resp_id, results=self.results, error=self.error
        )

    @classmethod
    def from_rpc(cls, message: str) -> "ResponseMessage":
        """load message from rpc

        Raises:
            json.JSONDecodeError"""

        parsed = json.loads(message)
        return cls(parsed["id"], parsed["results"], parsed["error"])


def request(message: str, host: str = "127.0.0.1", port: int = 8088) -> str:
    """handle socket request

    Raises:
        InvalidInput
        InvalidResponse
        ServerOffline
    """

    if not isinstance(message, str):
        raise InvalidInput("required <class 'str'> expected %s" % type(message))

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as conn:
            conn.connect((host, port))
            conn.sendall(create_rpc_message(message))

            recv = []
            while True:
                data = conn.recv(1024)
                try:
                    recv.append(data)
                    content = get_rpc_content(b"".join(recv))
                except ContentIncomplete:
                    continue
                except ContentOverflow as err:
                    raise InvalidResponse from err
                else:
                    return content

    except ConnectionError:
        raise ServerOffline from None


def server_subproces(
    server_path: str, server_module: str, activate_path: str = None
) -> None:
    """server subprocess

    Raises:
        ServerError
    """

    activator = [] if not activate_path else activate_path + ["&&"]
    run_server_cmd = activator + ["python", "-m", server_module]
    logger.debug(run_server_cmd)

    workdir = server_path
    logger.debug(workdir)

    # use current environment if not defined
    # env = os.environ.copy() if not sys_env else sys_env

    try:
        if os.name == "nt":
            # linux subprocess module does not have STARTUPINFO
            # so only use it if on Windows
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.SW_HIDE | subprocess.STARTF_USESHOWWINDOW
            server_proc = subprocess.Popen(
                run_server_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=True,
                cwd=workdir,
                # env=env,
                startupinfo=si,
            )
        else:
            server_proc = subprocess.Popen(
                run_server_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=True,
                cwd=workdir,
                # env=env,
            )

        _, serr = server_proc.communicate()
        err_message = "\n".join(serr.decode().splitlines())

        if server_proc.returncode == 123:
            raise PortInUse(err_message)

        if server_proc.returncode == 1:
            logger.debug("server error:\n%s", err_message)
            raise ServerError(err_message)

    except PortInUse:
        logger.debug("OSError, port in use")
    except FileNotFoundError as err:
        logger.exception("python not found in path", exc_info=True)
        raise ServerError from err
    except Exception as err:
        logger.exception("cannot run_server", exc_info=True)
        raise ServerError from err


def run_server(server_path: str, server_module: str, activate_path: str = None) -> None:
    """running server thread

    Raises:
        ServerError
    """

    thread = threading.Thread(
        target=server_subproces, args=(server_path, server_module, activate_path,)
    )
    thread.start()


def ping(*args: "Any") -> "ResponseMessage":
    """ping test

    Raises:
        ServerOffline
    """

    message = RequestMessage("ping", args)
    response = request(message.to_rpc())
    return ResponseMessage.from_rpc(response)


def initialize(*args: "Any") -> "ResponseMessage":
    """initialize server"""
    # temprorarily use ping to tests connection
    return ResponseMessage.from_rpc(ping(*args))


def shutdown(*args: "Any") -> "ResponseMessage":
    """shutdown server

    Raises:
        InvalidInput
        InvalidResponse
        ServerOffline
    """

    message = RequestMessage("exit", args)
    response = request(message.to_rpc())
    return ResponseMessage.from_rpc(response)


def change_workspace(workspace_dir: str) -> "ResponseMessage":
    """change workspace directory

    Raises:
        InvalidInput
        InvalidResponse
        ServerOffline
    """

    message = RequestMessage("document.changeWorkspace")
    message.params = {"uri": workspace_dir}
    response = request(message.to_rpc())
    return ResponseMessage.from_rpc(response)
