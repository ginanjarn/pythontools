"""service"""


from re import findall
import os
import socket
import subprocess
import logging
import json
from random import random
import threading

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


class InvalidResponse(Exception):
    """Invalid response"""


class ServerError(Exception):
    """Unable to run server"""


class ServerOffline(ConnectionError):
    """Server offline"""


RPC_SEPARATOR = b"\r\n\r\n"


def get_rpc_content(message: bytes) -> str:
    """get rpc content"""

    splitted_messages = message.split(RPC_SEPARATOR)
    if len(splitted_messages) != 2:
        raise InvalidResponse

    header, content = splitted_messages

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
        """convert to rpc message"""
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
    def from_rpc(cls, message):
        parsed = json.loads(message)
        return cls(parsed["id"], parsed["results"], parsed["error"])


def request(message: str, host: str = "127.0.0.1", port: int = 8088) -> str:
    """handle socket request

    Raises:
        ConnectionError
        InvalidResponse
    """
    try:
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
    except ConnectionError:
        raise ServerOffline from None


def server_subproces(activate_path=None) -> None:
    """server subprocess

    Raises:
        ServerError
    """
    activator = [] if not activate_path else activate_path+["&&"]
    run_server_cmd = activator+["python", "-m", "core.server.main"]
    logger.debug(run_server_cmd)

    def get_parent(path, level=1):
        """get leveled dirname"""
        new_path = path
        for _ in range(level):
            new_path = os.path.dirname(new_path)
        return new_path

    workdir = get_parent(os.path.abspath(__file__), 2)
    logger.debug(__file__)
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
        if server_proc.returncode != 0:
            logger.error("server error\n%s", serr.decode().replace(os.linesep, "\n"))
            raise ServerError
    except FileNotFoundError:
        logger.exception("python not found in path", exc_info=True)
        raise ServerError from None
    except OSError:
        logger.debug("OSError, port in use")
    except Exception:
        logger.exception("cannot run_server", exc_info=True)
        raise ServerError from None


def run_server(activate_path=None) -> None:
    """running server thread

    Raises:
        ServerError
    """

    logger.debug(activate_path)

    thread = threading.Thread(target=server_subproces, args=(activate_path,))
    thread.start()


def request_task(message: "Union[RequestMessage, str]") -> "Dict[str, Any]":
    """request task"""

    if isinstance(message, RequestMessage):
        v_message = message.to_rpc()
    else:
        v_message = message

    return request(v_message)


def ping(*args) -> "ResponseMessage":
    """ping test"""

    return request_task(RequestMessage("ping", args))


def initialize(*args):
    """initialize server"""
    # temprorarily use ping to tests connection
    return ResponseMessage.from_rpc(ping(*args))


def shutdown(*args) -> "ResponseMessage":
    """shutdown server"""

    message = RequestMessage("exit", args)
    response = request_task(message)
    response_message = ResponseMessage.from_rpc(response)
    return response_message


def complete(src: str, line: str, character: str) -> "ResponseMessage":
    """get completion data"""

    message = RequestMessage("textDocument.completion")
    message.params = {
        "uri": src,
        "location": {"line": line, "character": character},
    }
    response = request_task(message.to_rpc())
    response_message = ResponseMessage.from_rpc(response)
    return response_message


def hover(src: str, line: str, character: str) -> "ResponseMessage":
    """get sublime formatted documentation data"""

    message = RequestMessage("textDocument.hover")
    message.params = {
        "uri": src,
        "location": {"line": line, "character": character},
    }
    logger.debug(message)
    response = request_task(message.to_rpc())
    response_message = ResponseMessage.from_rpc(response)
    return response_message


def document_format(src: str) -> "ResponseMessage":
    """get sublime formatted PEP formatted data"""

    message = RequestMessage("textDocument.formatting")
    message.params = {"uri": src}
    response = request_task(message.to_rpc())
    response_message = ResponseMessage.from_rpc(response)
    return response_message


def change_workspace(workspace_dir: str) -> "ResponseMessage":
    """change workspace directory"""

    message = RequestMessage("document.changeWorkspace")
    message.params = {"uri": workspace_dir}
    response = request_task(message.to_rpc())
    response_message = ResponseMessage.from_rpc(response)
    return response_message
