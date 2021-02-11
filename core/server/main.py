"""main operation"""


from re import findall
import json
import socket
import sys
import logging

# TODO: Clean up later
# import service
from . import service


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


class InvalidMethod(KeyError):
    """unable to find method"""


class InvalidParams(KeyError):
    """unable to get required params"""


RPC_SEPARATOR = b"\r\n\r\n"


def get_rpc_content(message: bytes) -> str:
    """get rpc content"""

    try:
        header, content = message.split(RPC_SEPARATOR)
    except ValueError:
        raise ContentInvalid from None

    def content_length(header: bytes) -> int:
        """get content length"""
        decoded = header.decode("ascii")
        found = findall(r"Content-Length: (\d*)\s?", decoded)
        if not any(found):
            raise ValueError("unable fetch content length from '%s'" % decoded)
        return int(found[0])

    if len(content) < content_length(header):
        raise ContentIncomplete
    if len(content) > content_length(header):
        raise ContentOverflow
    return content.decode("utf-8")


def create_rpc_message(message: str) -> bytes:
    """create rpc message"""
    content_encoded = message.encode("utf-8")
    header = "Content-Length: %s" % (len(content_encoded))
    return b"%s%s%s" % (header.encode("ascii"), RPC_SEPARATOR, content_encoded)


class RequestMessage:
    """Request message helper"""

    def __init__(self, id: str, method: str, params: "Dict[str,Any]") -> None:
        self.id = id
        self.method = method
        self.params = params

    @classmethod
    def from_rpc(cls, message: str) -> "RequestMessage":
        loaded = json.loads(message)
        return cls(loaded["id"], loaded["method"], loaded["params"])


class Server:
    """Server engine"""

    @staticmethod
    def listen(
        callback: "Callable[[str],str]", host: str = "127.0.0.1", port: int = 8088
    ) -> None:
        """listen socket request"""

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((host, port))
            s.listen()
            conn, addr = s.accept()
            with conn:
                print("Connected by", addr)
                recv = []
                while True:
                    data = conn.recv(1024)
                    try:
                        recv.append(data)
                        logger.debug(recv)
                        content = get_rpc_content(b"".join(recv))
                    except ContentInvalid:
                        logger.error("content invalid")
                        break
                    except ContentIncomplete:
                        continue
                    except ContentOverflow:
                        logger.error("content overflow")
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

    def __init__(self):
        self.service = {}
        self.capability = []
        self.next = True

        self.workspace_directory = ""

    def register_service(
        self, method: str, callback: "Callback[Dict[str, Any]Optional[Any]]"
    ) -> None:
        """Register service capability"""
        self.service[method] = callback

    def do(self, message: str) -> str:
        """do operation"""

        id_ = -1
        results = None
        error = None

        try:
            parsed = RequestMessage.from_rpc(message)
        except json.JSONDecodeError as err:
            logger.debug("invalid message", exc_info=True)
            error = "invalid message : %s" % (str(err))
            return json.dumps({"id": id_, "results": results, "error": error})

        try:
            id_ = parsed.id
            method = self.service.get(parsed.method)
            if not method:
                raise InvalidMethod
            results = method(parsed.params)
        except InvalidParams as err:
            logger.debug("invalid params", exc_info=True)
            error = "invalid params : %s" % (str(err))
        except InvalidMethod as err:
            logger.debug("method not found", exc_info=True)
            error = "method not found : %s" % (str(err))
        except Exception as err:
            logger.error("internal error", exc_info=True)
            error = "internal error : %s" % (str(err))

        return json.dumps({"id": id_, "results": results, "error": error})

    def main_loop(self, once=False):
        """server main loop"""

        self.next = False if once else True

        # loop until interrupted
        while True:
            if not self.next:
                break
            Server.listen(self.do)

    def ping(self, params: "Dict[str, Any]") -> "Dict[str, Any]":
        logger.info("ping\nmessage = %s", params)
        return params

    def exit(self, params: "Dict[str, Any]") -> "Dict[str, Any]":
        logger.info("exit")
        self.next = False
        return None

    def completion(self, params: "Dict[str, Any]") -> "Dict[str, Any]":
        # TODO: build schenario
        path = ""
        proj = (
            None
            if not self.workspace_directory
            else service.jedi_project(self.workspace_directory)
        )
        try:
            src = params["uri"]
            line = params["location"]["line"]
            character = params["location"]["character"]

            line += 1  # jedi use 1 based index
            return service.complete(
                source=src, line=line, column=character, path=path, project=proj
            )
        except KeyError as err:
            raise InvalidParams(str(err)) from err
        except ValueError as err:
            raise InvalidParams(str(err)) from err

    def hover(self, params: "Dict[str, Any]") -> "Dict[str, Any]":
        # TODO: build schenario
        path = ""
        proj = (
            None
            if not self.workspace_directory
            else service.jedi_project(self.workspace_directory)
        )
        try:
            src = params["uri"]
            line = params["location"]["line"]
            character = params["location"]["character"]

            line += 1  # jedi use 1 based index
            return service.get_documentation(
                source=src, line=line, column=character, path=path, project=proj
            )
        except KeyError as err:
            raise InvalidParams(str(err)) from err
        except ValueError as err:
            raise InvalidParams(str(err)) from err

    def document_format(self, params: "Dict[str, Any]") -> "Dict[str, Any]":
        # TODO: build schenario
        try:
            src = params["uri"]
            return service.format_document(src)
        except KeyError as err:
            raise InvalidParams(str(err)) from err
        except ValueError as err:
            raise InvalidParams(str(err)) from err

    def change_workspace(self, params: "Dict[str, Any]") -> "Dict[str, Any]":
        # TODO: build schenario
        try:
            path = params["uri"]
            self.workspace_directory = path
        except KeyError as err:
            raise InvalidParams(str(err)) from err
        except ValueError as err:
            raise InvalidParams(str(err)) from err
        else:
            return {"workspace_directory": self.workspace_directory}


def main():
    try:
        server = Server()
        server.register_service("ping", server.ping)
        server.register_service("exit", server.exit)
        server.register_service("textDocument.completion", server.completion)
        server.register_service("textDocument.hover", server.hover)
        server.register_service("textDocument.formatting", server.document_format)
        server.register_service("document.changeWorkspace", server.change_workspace)

        server.main_loop()

    except OSError:
        logger.debug("port in use")
        sys.exit(123)
    except Exception:
        logger.fatal("unexpectedd error", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
