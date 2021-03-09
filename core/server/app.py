"""main operation"""


from re import findall
import json
import os
import socket
import sys
import logging
from typing import Callable, Text, Dict, Any
from importlib.util import find_spec

from . import service


logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)
sh = logging.StreamHandler()
sh.setFormatter(logging.Formatter("%(levelname)s\t%(module)s: %(lineno)d\t%(message)s"))
sh.setLevel(logging.DEBUG)
fh = logging.FileHandler("server.log")
fh.setFormatter(logging.Formatter("%(levelname)s\t%(module)s: %(lineno)d\t%(message)s"))
fh.setLevel(logging.ERROR)
logger.addHandler(sh)
logger.addHandler(fh)


class ContentIncomplete(ValueError):
    """Content incomplete"""


class ContentOverflow(ValueError):
    """Content too large"""


class ContentInvalid(ValueError):
    """Content invalid"""


class InvalidMethod(KeyError):
    """unable to find method"""


class InvalidParams(KeyError):
    """unable to get required params"""


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
    header = "Content-Length: %s" % (len(content_encoded))
    return b"%s%s%s" % (header.encode("ascii"), RPC_SEPARATOR, content_encoded)


class RequestMessage:
    """Request message helper"""

    def __init__(self, id_: str, method: str, params: "Dict[str,Any]") -> None:
        self.id_ = id_
        self.method = method
        self.params = params

    @classmethod
    def from_rpc(cls, message: str) -> "RequestMessage":
        """load RequestMessage from rpc

        Result:
            RequestMessage

        Raises:
            json.JSONDecodeError"""
        loaded = json.loads(message)
        return cls(loaded["id"], loaded["method"], loaded["params"])


class ResponseMessage:
    """Response message"""

    def __init__(
        self,
        id_: int,
        *,
        results: "Dict[str, Any]" = None,
        error: "Dict[str, Any]" = None
    ) -> None:
        self.id_ = id_
        self.results = results
        self.error = error

    def __repr__(self) -> str:
        return "{id_}\n{results}\n{error}\n".format(
            id_=self.id_, results=self.results, error=self.error
        )

    def to_rpc(self) -> str:
        """export to rpc

        Results:
            JSON string

        Raises:
            TypeError"""
        return json.dumps(
            {"id": self.id_, "results": self.results, "error": self.error}
        )


class Server:
    """Server engine"""

    def __init__(self) -> None:
        self.service = {}
        self.capability = []
        self.next = True

        self.workspace_directory = ""

    @staticmethod
    def on_listening(sock: socket.socket, *, callback: Callable[[Text], Text]) -> None:
        """on listening process"""

        conn, addr = sock.accept()
        print("Connected by", addr)
        with conn:
            recv = []
            content = ""
            while True:
                data = conn.recv(1024)
                try:
                    recv.append(data)
                    logger.debug(recv)
                    content = get_rpc_content(b"".join(recv))
                except ContentInvalid:
                    break
                except ContentIncomplete:
                    continue
                except ContentOverflow:
                    break
                else:
                    logger.debug(content)
                    break

            try:
                result = callback(content)
            except Exception:
                logger.exception("internal error")
                result = (
                    '{"jsonrpc":"2.0","id":null,"'
                    '"error":{"code":1,"message":"invalid request"}}'
                )
            logger.debug(result)
            conn.sendall(create_rpc_message(result))

    def listen(self, host: str = "127.0.0.1", port: int = 8088) -> None:
        """listen socket request"""

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind((host, port))
            sock.listen()
            while True:
                # process request
                self.on_listening(sock, callback=self.process)

                # continue listening
                if not self.next:
                    break

    def register_service(
        self, method: str, callback: "Callback[Dict[str, Any]Optional[Any]]"
    ) -> None:
        """Register service capability"""

        self.service[method] = callback

    def process(self, message: str) -> str:
        """process operation

        Results:
            ResponseMessage json string
        """

        try:
            parsed = RequestMessage.from_rpc(message)
        except json.JSONDecodeError as err:
            logger.debug("invalid message", exc_info=True)
            error = "invalid message : %s" % err
            return ResponseMessage(-1, error=error).to_rpc()

        response = ResponseMessage(-1)
        try:
            response.id_ = parsed.id_
            process_method = self.service.get(parsed.method)
            if not process_method:
                raise InvalidMethod(parsed.method)
            response.results = process_method(parsed.params)

        except InvalidParams as err:
            response.error = "invalid params : %s" % err
        except InvalidMethod as err:
            response.error = "method not found : %s" % err
        except Exception as err:
            logger.debug("internal error", exc_info=True)
            response.error = "internal error : %s" % err

        return response.to_rpc()

    @staticmethod
    def ping(params: "Dict[str, Any]") -> "Dict[str, Any]":
        logger.info("ping\nmessage = %s", params)
        return params

    @staticmethod
    def isinstalled(package: Text) -> bool:
        """check if module installed"""
        return True if find_spec(package) else False

    def initialize(self, params: Dict[Text, Any]) -> Dict[Text, Any]:
        """initialize"""

        return {
            "completion": self.isinstalled("jedi"),
            "hover": self.isinstalled("jedi"),
            "document_format": self.isinstalled("black"),
            "diagnostic": self.isinstalled("pylint"),
            "rename": self.isinstalled("rope"),
        }

    def exit(self, params: "Dict[str, Any]") -> None:
        logger.info("exit")
        self.next = False
        return None

    def completion(self, params: "Dict[str, Any]") -> "Dict[str, Any]":
        """completion

        Raises:
            InvalidParams
            """

        project = (
            None
            if not self.workspace_directory
            else service.jedi_project(self.workspace_directory)
        )
        try:
            src = params["uri"]
            line = params["location"]["line"]
            character = params["location"]["character"]

            line += 1  # jedi use 1 based index
            completions = service.complete(
                src, line=line, column=character, project=project
            )
            return service.to_rpc(completions)
        except KeyError as err:
            raise InvalidParams from err
        except ValueError as err:
            raise InvalidParams from err

    def hover(self, params: "Dict[str, Any]") -> "Dict[str, Any]":
        """hover

        Raises:
            InvalidParams"""

        project = (
            None
            if not self.workspace_directory
            else service.jedi_project(self.workspace_directory)
        )
        try:
            src = params["uri"]
            line = params["location"]["line"]
            character = params["location"]["character"]

            line += 1  # jedi use 1 based index
            helps = service.get_documentation(
                src, line=line, column=character, project=project
            )
            return service.to_rpc(helps)
        except KeyError as err:
            raise InvalidParams from err
        except ValueError as err:
            raise InvalidParams from err

    @staticmethod
    def document_format(params: "Dict[str, Any]") -> "Dict[str, Any]":
        """document format

        Raises:
            InvalidParams"""

        try:
            src = params["uri"]
            results = service.format_document(src)
            return service.to_rpc(results, source=src)
        except KeyError as err:
            raise InvalidParams from err
        except ValueError as err:
            raise InvalidParams from err

    def change_workspace(self, params: "Dict[str, Any]") -> "Dict[str, Any]":
        """change workspace configg

        Raises:
            InvalidParams"""

        try:
            path = params["uri"]
            self.workspace_directory = path
        except KeyError as err:
            raise InvalidParams from err
        except ValueError as err:
            raise InvalidParams from err
        else:
            return {"workspace_directory": self.workspace_directory}

    def get_diagnostic(self, params: "Dict[str, Any]") -> "Dict[str, Any]":
        """get diagnostic

        Raises:
            InvalidParams"""

        try:
            path = params["uri"]
            return service.lint(path)
        except KeyError as err:
            raise InvalidParams from err
        except ValueError as err:
            raise InvalidParams from err

    def rename(self, params: "Dict[str, Any]") -> "Dict[str, Any]":
        """rename

        Raises:
            InvalidParams"""

        try:
            path = params["uri"]
            project_path = os.path.dirname(path)  # project limited to current directory
            offset = params.get("location", None)
            new_name = params["new_name"]

            changes = service.rename_attribute(
                project_path=project_path,
                resource_path=path,
                offset=offset if offset and offset > 0 else None,
                new_name=new_name,
            )

            return service.to_rpc(changes)
        except KeyError as err:
            raise InvalidParams from err
        except ValueError as err:
            raise InvalidParams from err


def main():
    """main app"""

    try:
        server = Server()
        server.register_service("ping", server.ping)
        server.register_service("initialize", server.initialize)
        server.register_service("exit", server.exit)
        server.register_service("textDocument.completion", server.completion)
        server.register_service("textDocument.hover", server.hover)
        server.register_service("textDocument.formatting", server.document_format)
        server.register_service("document.changeWorkspace", server.change_workspace)
        server.register_service("document.rename", server.rename)
        server.register_service("textDocument.get_diagnostic", server.get_diagnostic)

        server.listen()

    except OSError:
        logger.debug("port in use")
        sys.exit(123)
    except Exception:
        logger.fatal("unexpected error", exc_info=True)
        sys.exit(1)