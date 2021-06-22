"""remote handler"""


import io
import re
import os
import socket
import subprocess
import time
import json
import logging

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)
sh = logging.StreamHandler()
template = "%(asctime)s - %(levelname)s::%(module)s: %(lineno)d\t%(message)s"
sh.setFormatter(logging.Formatter(template))
sh.setLevel(logging.DEBUG)
logger.addHandler(sh)


# TransactionMessage separator
HEADER_ITEMS_SEPARATOR = b"\r\n"
BODY_SEPARATOR = b"\r\n\r\n"


class TransactionMessage:
    """Transaction message

    Property:
    * content: str
        message content

    * encoding: str
        content encoding

    * _headers: dict
        message headers
    """

    def __init__(self, content, encoding="utf-8", headers=None):
        self._content_encoded = content.encode(encoding)
        self.encoding = encoding
        self._headers = {
            "Content-Length": len(self._content_encoded),
            "encoding": self.encoding,
        }

    @property
    def content(self) -> str:
        return self._content_encoded.decode(self.encoding)

    @staticmethod
    def _generate_header_item(headers, encoding="ascii"):
        for key, value in headers.items():
            yield "{key}: {value}".format(key=key, value=value).encode(encoding)

    def to_bytes(self) -> bytes:
        """generate encoded message"""

        merged_headers = HEADER_ITEMS_SEPARATOR.join(
            self._generate_header_item(self._headers)
        )
        return BODY_SEPARATOR.join([merged_headers, self._content_encoded])

    @staticmethod
    def _parse_header(header: bytes, encoding: str = "ascii"):
        """parse header items"""

        parsed = {}
        decoded_header = header.decode(encoding)

        for line in decoded_header.splitlines():
            matches = re.findall(r"(.*): (.*)\s?", line)
            for match in matches:
                parsed[match[0]] = match[1]

        return parsed

    @classmethod
    def from_bytes(cls, data: bytes):
        """create message from encoded bytes"""

        header, body = data.split(BODY_SEPARATOR)

        parsed_header = TransactionMessage._parse_header(header)
        required_size = int(parsed_header.get("Content-Length"))
        if len(body) != required_size:
            raise ValueError(
                "content corrupted, want=%d, expected=%d" % (required_size, len(body))
            )

        return cls(
            content=body.decode(parsed_header.get("encoding", "utf-8")),
            headers=parsed_header,
        )


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
    def builder(cls, method=None, params=None):
        id_ = str(time.time())
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
    def builder(cls, results=None, error=None):
        id_ = str(time.time())
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

    Parameters:
        message: str
            socket message

        host: str
            target host name

        port: int
            target port

        timeout: int or None
            set timeout. socket blocking mode if timeout is None. non blocking if
            timeout = 0.

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
            conn.sendall(TransactionMessage(message).to_bytes())

            downloaded = io.BytesIO()
            buf_size = 4096

            while True:
                data = conn.recv(buf_size)
                downloaded.write(data)

                if len(data) < buf_size:
                    break

            logger.debug(downloaded.getvalue())
            return TransactionMessage.from_bytes(downloaded.getvalue()).content

    except socket.timeout as err:
        return ResponseMessage.builder("-1", error=repr(err)).to_rpc()

    except ConnectionError as err:
        raise ServerOffline(err) from None


def run_server(
    server_path: str, *, interpreter_path: str = None, activate_path: str = None
) -> None:

    """server subprocess

    Parameter:
        server_path: str
            path to server script

        activate_path: str
            path to activate environment executable

    Raises:
        ServerError
    """

    activator = [] if not activate_path else activate_path + ["&&"]
    interpreter = interpreter_path if interpreter_path else "python"
    run_server_cmd = activator + [interpreter, server_path]
    logger.debug(run_server_cmd)

    workdir = os.path.dirname(server_path)
    logger.debug(workdir)

    try:
        if os.name == "nt":
            # if on Windows, hide process window
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.SW_HIDE | subprocess.STARTF_USESHOWWINDOW
        else:
            startupinfo = None

        server_proc = subprocess.Popen(
            run_server_cmd,
            shell=True,
            cwd=workdir,
            # env=env,
            startupinfo=startupinfo,
        )

        time.sleep(3)  # wait server ready
        err_message = None
        poll = server_proc.poll()
        if poll:
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


def ping(*args: "Any") -> "ResponseMessage":
    """ping test

    Raises:
        ServerOffline
    """

    message = RequestMessage.builder("ping", args)
    response = request(message.to_rpc(), timeout=0.5)
    return ResponseMessage.from_rpc(response)


def initialize(*args: "Any") -> "ResponseMessage":
    """initialize server"""

    message = RequestMessage.builder("initialize", args)
    response = request(message.to_rpc(), timeout=30)
    return ResponseMessage.from_rpc(response)


def shutdown(*args: "Any") -> "ResponseMessage":
    """shutdown server

    Raises:
        InvalidInput
        InvalidResponse
        ServerOffline
    """

    message = RequestMessage.builder("exit", args)
    response = request(message.to_rpc(), timeout=15)
    return ResponseMessage.from_rpc(response)


def change_workspace(workspace_dir: str) -> "ResponseMessage":
    """change workspace directory

    Raises:
        InvalidInput
        InvalidResponse
        ServerOffline
    """

    message = RequestMessage.builder("document.changeWorkspace")
    message.params = {"uri": workspace_dir}
    response = request(message.to_rpc(), timeout=15)
    return ResponseMessage.from_rpc(response)
