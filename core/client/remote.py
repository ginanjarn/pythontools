"""remote handler"""


from re import findall
import os
import socket
import subprocess
import json
import random
import logging

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)
sh = logging.StreamHandler()
sh.setFormatter(logging.Formatter("%(levelname)s\t%(module)s: %(lineno)d\t%(message)s"))
sh.setLevel(logging.DEBUG)
logger.addHandler(sh)


RPC_SEPARATOR = b"\r\n\r\n"


def get_content_length(header: bytes):
    """get content length"""

    found = findall(r"Content-Length: (\d*)\s?", header.decode("ascii"))
    if not any(found):
        raise ValueError("unable to get Content-Length in header")

    return int(found[0])


def get_rpc_content(message: bytes) -> str:
    separated = message.split(RPC_SEPARATOR)

    if len(separated) != 2:
        raise ValueError("unable to separate header and body")

    content_length = get_content_length(separated[0])

    if len(separated[1]) != content_length:
        raise ValueError(
            "invalid content length, required : %s, expected : %s"
            % (content_length, len(separated[1]))
        )

    return separated[1].decode("utf-8")


def create_rpc_content(message: str) -> bytes:
    content_encoded = message.encode("utf-8")
    content_length = len(content_encoded)
    header = bytes("Content-Length: %d" % content_length, "ascii")

    return b"".join([header, RPC_SEPARATOR, content_encoded])


# fmt: off

# RPC KEYS
ID          = "id"
METHOD      = "method"
PARAMS      = "params"
RESULTS     = "results"
ERROR       = "error"

# fmt: on

# Transaction classes +++++++++++++++++++++++++++++++++


class RequestMessage(dict):
    """request message"""

    @property
    def id_(self):
        return self[ID]

    @id_.setter
    def id_(self, id_):
        self[ID] = id_

    @property
    def method(self):
        return self[METHOD]

    @property
    def params(self):
        return self[PARAMS]

    @params.setter
    def params(self, par):
        self[PARAMS] = par

    @classmethod
    def builder(cls, id_, method=None, params=None):
        return cls({ID: id_, METHOD: method, PARAMS: params})

    @classmethod
    def from_rpc(cls, message: str) -> "RequestMessage":
        return cls(json.loads(message))

    def to_rpc(self) -> str:
        return json.dumps(self)


class ResponseMessage(dict):
    """response message"""

    @property
    def id_(self):
        return self[ID]

    @id_.setter
    def id_(self, id_):
        self[ID] = id_

    @property
    def results(self):
        return self[RESULTS]

    @results.setter
    def results(self, res):
        self[RESULTS] = res

    @property
    def error(self):
        return self[ERROR]

    @error.setter
    def error(self, err):
        self[ERROR] = err

    @classmethod
    def builder(cls, id_, results=None, error=None):
        return cls({ID: id_, RESULTS: results, ERROR: error})

    @classmethod
    def from_rpc(cls, message: str) -> "ResponseMessage":
        return cls(json.loads(message))

    def to_rpc(self) -> str:
        return json.dumps(self)


# Error classes ++++++++++++++++++++++++++++++++++++++++
class InvalidRPCMessage(ValueError):
    """Invalid RPC Message"""

    def __init__(self, err):
        super().__init__("InvalidRPCMessage : %s" % repr(err))


class ServerError(Exception):
    """Server error"""

    def __init__(self, err):
        super().__init__("ServerError : %s" % repr(err))


class ServerOffline(Exception):
    """Server offline"""


class PortInUse(OSError):
    """Port in use"""

    def __init__(self, err):
        super().__init__("PortInUse : %s" % repr(err))


# ++++++++++++++++++++++++++++++++++++++++++++++++++++++


def request(
    message: str,
    *,
    host: str = "127.0.0.1",
    port: int = 8088,
    timeout: "Optional[float]" = None  # None will blocking
) -> str:
    """handle socket request

    Raises:
        InvalidInput
        InvalidResponse
        ServerOffline
    """

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as conn:
            conn.settimeout(timeout)
            conn.connect((host, port))

            logger.debug(message)
            conn.sendall(create_rpc_content(message))

            downloaded = []
            buf_size = 4096

            while True:
                data = conn.recv(buf_size)
                downloaded.append(data)

                if len(data) < buf_size:
                    break
            logger.debug(downloaded)
            return get_rpc_content(b"".join(downloaded))

    except socket.timeout as err:
        return ResponseMessage.builder("-1", error=repr(err)).to_rpc()

    except ConnectionError as err:
        raise ServerOffline(err) from None


def run_server(server_path: str, activate_path: str = None) -> "process":
    """server subprocess

    Raises:
        ServerError
    """

    activator = [] if not activate_path else activate_path + ["&&"]
    run_server_cmd = activator + ["python", server_path]
    logger.debug(run_server_cmd)

    workdir = os.path.dirname(server_path)
    logger.debug(workdir)

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

        if server_proc.poll():
            _, serr = server_proc.communicate()
            err_message = "\n".join(serr.decode().splitlines())

            if server_proc.returncode == 123:
                raise PortInUse(err_message)

            if server_proc.returncode == 1:
                logger.debug("server error:\n%s", err_message)
                raise ServerError(err_message)

        else:
            # pool() return None if child process running

            logger.debug("server activated")

    except PortInUse:
        logger.debug("OSError, port in use")

    except FileNotFoundError as err:
        logger.exception("python not found in path", exc_info=True)
        raise ServerError(err) from err

    except Exception as err:
        logger.exception("cannot run_server", exc_info=True)
        raise ServerError(err) from err

    return server_proc


def generate_id() -> str:
    """generate request id"""
    return str(random.random())


def ping(*args: "Any") -> "ResponseMessage":
    """ping test

    Raises:
        ServerOffline
    """

    message = RequestMessage.builder(generate_id(), "ping", args)
    response = request(message.to_rpc(), timeout=0.5)
    return ResponseMessage.from_rpc(response)


def initialize(*args: "Any") -> "ResponseMessage":
    """initialize server"""

    message = RequestMessage.builder(generate_id(), "initialize", args)
    response = request(message.to_rpc(), timeout=30)
    return ResponseMessage.from_rpc(response)


def shutdown(*args: "Any") -> "ResponseMessage":
    """shutdown server

    Raises:
        InvalidInput
        InvalidResponse
        ServerOffline
    """

    message = RequestMessage.builder(generate_id(), "exit", args)
    response = request(message.to_rpc(), timeout=0.5)
    return ResponseMessage.from_rpc(response)


def change_workspace(workspace_dir: str) -> "ResponseMessage":
    """change workspace directory

    Raises:
        InvalidInput
        InvalidResponse
        ServerOffline
    """

    message = RequestMessage.builder(generate_id(), "document.changeWorkspace")
    message.params = {"uri": workspace_dir}
    response = request(message.to_rpc(), timeout=0.5)
    return ResponseMessage.from_rpc(response)
