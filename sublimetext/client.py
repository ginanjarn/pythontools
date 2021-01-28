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


class ServerError(Exception):
    """Unable to run server"""


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
    logger.debug(content_encoded)
    header = "Content-Length: %s"%(len(content_encoded))
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

    def __repr__(self)->str:
        return "id : {req_id}, method : {method}, params : {params}".format(
            req_id=self.req_id, method=self.method, params=self.params)

    def to_rpc(self) -> str:
        """convert to rpc message"""
        message = {"id": self.req_id, "method": self.method, "params": self.params}
        return json.dumps(message)

class ResponseMessage:
    """Response message helper"""

    def __init__(self, resp_id: str, results: "Optional[Any]" = None, error: "Optional[Any]" = None) -> None:
        self.resp_id = resp_id
        self.results = results
        self.error = error

    def __repr__(self)->str:
        return "id : {resp_id}, results : {results}, error : {error}".format(
            resp_id=self.req_id, results=self.results, error=self.error)

    @classmethod
    def from_rpc(cls, message):
        parsed = json.loads(message)
        return cls(parsed["id"],parsed["results"],parsed["error"])


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

    @staticmethod
    def run_server_subproces(sys_env=None):
        """run server subprocess"""

        run_server_cmd = ["python", "-m", "core.server.main"]
        logger.debug(run_server_cmd)

        def get_parent(path, level=1):
            """get leveled dirname"""
            new_path = path
            for _ in range(level):
                new_path = os.path.dirname(new_path)
            return new_path

        workdir = get_parent(os.path.abspath(__name__), 2)
        logger.debug(workdir)

        # use current environment if not defined
        env = os.environ.copy() if not sys_env else sys_env

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
                    env=env,
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
                    env=env,
                )

            _, serr = server_proc.communicate()
            if server_proc.returncode != 0:
                logger.error(
                    "server error\n%s", serr.decode().replace(os.linesep, "\n")
                )
                raise ServerError
        except FileNotFoundError:
            logger.exception("python not found in path", exc_info=True)
            raise ServerError from None
        except OSError:
            logger.debug("OSError")
        except Exception:
            logger.exception("cannot run_server", exc_info=True)
            raise ServerError from None

    def __init__(self) -> None:
        # server is running
        self.server_online = False
        # server error
        self.server_error = False
        # busy
        self.busy = False


    def run_server(self, sys_env=None):
        """running server thread"""
        if self.server_online:
            return

        def server_task(parent, sys_env=None):
            try:
                parent.server_online = True
                Service.run_server_subproces(sys_env)
            except ServerError:
                parent.server_error = True
            finally:
                parent.server_online = False

        thread = threading.Thread(target=server_task, args=(self, sys_env))
        if not self.server_online:
            thread.start()    

    def reload_server(self):
        """reload server"""
        self.server_error = False
        self.run_server()

    def request_task(self, message: "Union[RequestMessage, str]"):
        """request task"""
        if isinstance(message, RequestMessage):
            v_message = message.to_rpc()
        else:
            v_message = message

        logger.debug(v_message)

        try:
            self.busy = True
            result = Service.request(v_message)
        except ConnectionError:
            if not self.server_error:
                # Autorun server entry point ++++++++++
                self.run_server()
                return self.request_task(v_message)
        else:
            self.server_online = True
            return result
        finally:
            self.busy = False

    def ping(self, *args):
        # ping test
        return self.request_task(RequestMessage("ping", args))

    def exit(self, *args):
        # exit server
        self.server_online = False
        message = RequestMessage("exit", args)
        response = self.request_task(message)
        response_message = ResponseMessage.from_rpc(response)
        if response_message.resp_id == message.req_id:
            return response_message.results

    def complete(self, src: str, line: str, character: str) -> "Dict[str, str]":
        """get sublime formatted completion data"""
        message = RequestMessage("textDocument.completion")
        message.params = {
            "uri": src,
            "location": {"line": line, "character": character},
        }
        response = self.request_task(message.to_rpc())
        response_message = ResponseMessage.from_rpc(response)
        if response_message.resp_id == message.req_id:
            return response_message.results

    def hover(self, src: str, line: str, character: str) -> "Dict[str, str]":
        """get sublime formatted documentation data"""
        message = RequestMessage("textDocument.hover")
        message.params = {
            "uri": src,
            "location": {"line": line, "character": character},
        }
        logger.debug(message)
        response = self.request_task(message.to_rpc())
        response_message = ResponseMessage.from_rpc(response)
        if response_message.resp_id == message.req_id:
            return response_message.results

    def document_format(self, src: str) -> "Dict[str, str]":
        """get sublime formatted PEP formatted data"""
        message = RequestMessage("textDocument.formatting")
        message.params = {"uri": src}
        response = self.request_task(message.to_rpc())
        response_message = ResponseMessage.from_rpc(response)
        if response_message.resp_id == message.req_id:
            return response_message.results

    def change_workspace(self, workspace_dir: str):
        """change workspace directory"""        

        message = RequestMessage("document.changeWorkspace")
        message.params = {"uri": workspace_dir}
        response = self.request_task(message.to_rpc())
        response_message = ResponseMessage.from_rpc(response)
        if response_message.resp_id == message.req_id:
            return response_message.results