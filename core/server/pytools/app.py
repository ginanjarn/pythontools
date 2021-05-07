"""main server"""

import argparse
import io
import json
import logging
import os
import socketserver
import socket
import sys
import signal
import re

from importlib.util import find_spec
from typing import Any, Tuple

from api import rpc
from api import completion, hover, document_formatting, rename, analyzer


logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)
sh = logging.StreamHandler()
template = "%(asctime)s - %(levelname)s::%(module)s: %(lineno)d\t%(message)s"
sh.setFormatter(logging.Formatter(template))
sh.setLevel(logging.DEBUG)
fh = logging.FileHandler("server.log")
fh.setFormatter(logging.Formatter(template))
fh.setLevel(logging.ERROR)
logger.addHandler(sh)
logger.addHandler(fh)


class TransactionMessage:
    def __init__(self, content, encoding="utf-8", headers=None):
        self._content_encoded = content.encode(encoding)
        self.encoding = encoding
        self._headers = {
            "Content-Length": len(self._content_encoded),
            "encoding": self.encoding,
        }

    @property
    def content(self):
        return self._content_encoded.decode(self.encoding)

    def to_bytes(self):
        headers = []
        for key, value in self._headers.items():
            headers.append(f"{key}: {value}".encode(self.encoding))

        merged_headers = b"\r\n".join(headers)
        return b"\r\n\r\n".join([merged_headers, self._content_encoded])

    @staticmethod
    def parse_header(header: bytes) -> dict:
        parsed = {}
        for item in header.splitlines():
            decoded = item.decode("ascii")
            matches = re.findall(r"(.*): (.*)\s?", decoded)
            for match in matches:
                parsed[match[0]] = match[1]

        return parsed

    @classmethod
    def from_bytes(cls, data: bytes):
        header, body = data.split(b"\r\n\r\n")

        parsed_header = TransactionMessage.parse_header(header)
        required_size = int(parsed_header.get("Content-Length"))
        if len(body) != required_size:
            raise ValueError(
                "content corrupted, want=%d, expected=%d" % (required_size, len(body))
            )

        return cls(
            content=body.decode(parsed_header.get("encoding", "utf-8")),
            headers=parsed_header,
        )


# Error classes ++++++++++++++++++++++++++++++++++++++++
class InvalidRPCMessage(ValueError):
    """Invalid RPC Message"""

    def __init__(self, err):
        super().__init__("Invalid RPC Message : %s" % repr(err))


class MethodNotFound(KeyError):
    """Method not found error"""

    def __init__(self, err):
        super().__init__("method not found : %s" % str(err))


class InvalidParams(Exception):
    """required params not found"""

    def __init__(self, err):
        if isinstance(err, KeyError):
            # key not found
            super().__init__("params not found : %s" % str(err))
        else:
            # parsing error
            super().__init__(str(err))


class InternalError(Exception):
    """internal error occured"""


# fmt: off

TERMINATE           = False
WORKSPACE_DIRECTORY = None

# RPC COMMAND
PING                = "ping"
EXIT                = "exit"
INITIALIZE          = "initialize"
CHANGE_WORKPACE     = "document.changeWorkspace"
COMPLETION          = "textDocument.completion"
HOVER               = "textDocument.hover"
FORMATTING          = "textDocument.formatting"
RENAME              = "document.rename"
DIAGNOSTIC          = "textDocument.get_diagnostic"
VALIDATE            = "textDocument.validate"

# RPC FEATURE
F_COMPLETION        = "completion"
F_HOVER             = "hover"
F_FORMATTING        = "document_format"
F_RENAME            = "rename"
F_DIAGNOSTIC        = "diagnostic"
F_VALIDATE          = "validate"

# fmt: on
BUFF_SIZE = 4096
BUFFER = None
BUFFER_URI = None


class ServerHandler(socketserver.BaseRequestHandler):
    def __init__(
        self,
        request: socket.socket,
        client_address: Tuple[str, int],
        server: socketserver.TCPServer,
    ):
        self.request = request
        self.client_address = client_address
        self.server = server

        self.commands = {}

        self.setup()
        try:
            self.handle()
        finally:
            self.finish()

    def setup(self) -> None:
        self.commands[PING] = self.ping
        self.commands[EXIT] = self.exit
        self.commands[INITIALIZE] = self.initialize
        self.commands[CHANGE_WORKPACE] = self.change_workspace

        # features map ++++++++++++++++++++++++++++++++++++++++++
        self.commands[COMPLETION] = self.complete
        self.commands[HOVER] = self.hover
        self.commands[FORMATTING] = self.formatting
        self.commands[RENAME] = self.rename
        self.commands[DIAGNOSTIC] = self.get_diagnostic
        self.commands[VALIDATE] = self.validate_source

    def ping(self, params: rpc.Params) -> Any:
        return params

    def exit(self, params: Any) -> Any:
        global TERMINATE
        TERMINATE = True
        return None

    def initialize(self, params: rpc.Params) -> Any:

        # features capable +++++++++++++++++++++++++++++++++++++++
        return {
            F_COMPLETION: bool(find_spec("jedi")),
            F_HOVER: bool(find_spec("jedi")),
            F_FORMATTING: bool(find_spec("black")),
            F_RENAME: bool(find_spec("rope")),
            F_DIAGNOSTIC: bool(find_spec("pylint")),
            F_VALIDATE: bool(find_spec("pyflakes")),
            # "pid": os.getpid(),
        }

    def change_workspace(self, params: rpc.Params) -> Any:
        global WORKSPACE_DIRECTORY

        try:
            wparams = rpc.WorkspaceParams.from_rpc(params)
            WORKSPACE_DIRECTORY = wparams.uri
            results = {"workspace_directory": WORKSPACE_DIRECTORY}

        except (ValueError, KeyError) as err:
            raise InvalidParams(err) from err
        else:
            return results

    # features function +++++++++++++++++++++++++++++++++++++++++
    def complete(self, params: rpc.Params) -> Any:
        try:
            tparams = rpc.TextDocumentPositionParams.from_rpc(params)
            path = tparams.uri
            line = tparams.position.line + 1  # jedi use 1 based index
            column = tparams.position.character

        except (ValueError, KeyError) as err:
            raise InvalidParams(err) from err

        try:
            project = (
                completion.Project(WORKSPACE_DIRECTORY) if WORKSPACE_DIRECTORY else None
            )
            cmpl = completion.Completion(
                path, line=line, column=column, project=project
            )
            results = cmpl.to_rpc()

        except Exception as err:
            raise InternalError(err) from err
        else:
            return results

    def hover(self, params: rpc.Params) -> Any:
        try:
            tparams = rpc.TextDocumentPositionParams.from_rpc(params)
            path = tparams.uri
            line = tparams.position.line + 1  # jedi use 1 based index
            column = tparams.position.character

        except (ValueError, KeyError) as err:
            raise InvalidParams(err) from err

        try:
            project = (
                hover.Project(WORKSPACE_DIRECTORY) if WORKSPACE_DIRECTORY else None
            )

            doc = hover.Documentation(path, line=line, column=column, project=project)
            results = doc.to_rpc()

        except Exception as err:
            raise InternalError(err) from err
        else:
            return results

    def formatting(self, params: rpc.Params) -> Any:
        try:
            uri = rpc.DocumentURI.from_rpc(params)
            src = uri

        except (ValueError, KeyError) as err:
            raise InvalidParams(err) from err

        try:
            formatted = document_formatting.DocumentFormatting(src)
            results = formatted.to_rpc()

        except Exception as err:
            raise InternalError(err) from err
        else:
            return results

    def rename(self, params: rpc.Params) -> Any:
        try:
            path = params["uri"]

            project = (
                WORKSPACE_DIRECTORY if WORKSPACE_DIRECTORY else os.path.dirname(path)
            )

            resource = path
            offset = params["location"]
            new_name = params["new_name"]

        except (ValueError, KeyError) as err:
            raise InvalidParams(err) from err

        try:
            changes = rename.rename_attribute(project, resource, offset, new_name)
            results = rename.to_rpc(changes)

        except Exception as err:
            raise InternalError(err) from err
        else:
            return results

    def get_diagnostic(self, params: rpc.Params) -> Any:
        try:
            uri = rpc.DocumentURI.from_rpc(params)
        except (ValueError, KeyError) as err:
            raise InvalidParams(err) from err

        try:
            results = analyzer.lint(path=uri)
        except Exception as err:
            raise InternalError(err)
        else:
            return results

    def validate_source(self, params: rpc.Params) -> Any:
        try:
            uri = rpc.DocumentURI.from_rpc(params)
        except (ValueError, KeyError) as err:
            raise InvalidParams(err) from err

        try:
            results = analyzer.lint(path=uri, engine="pyflakes")
        except Exception as err:
            raise InternalError(err)
        else:
            return results

    # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

    def run(self, method: str, params: rpc.Params) -> Any:
        try:
            command = self.commands[method]
        except KeyError as err:
            raise MethodNotFound(err) from err
        else:
            return command(params)

    def handle_request(self, message: bytes) -> bytes:
        """handle request"""

        resp_message = rpc.ResponseMessage.builder("-1")

        try:
            # parsing requestcontent
            try:
                req_message = rpc.RequestMessage.from_rpc(
                    TransactionMessage.from_bytes(message).content
                )

            except json.JSONDecodeError as err:
                raise InvalidRPCMessage(err) from err

            resp_message.id_ = req_message.id_

        except Exception as err:
            logger.debug("loading message error", exc_info=True)
            resp_message.error = repr(err)
            return TransactionMessage(resp_message.to_rpc()).to_bytes()

        try:
            # processing

            results = self.run(req_message.method, req_message.params)
            resp_message.id_ = req_message.id_
            resp_message.results = results

        except Exception as err:
            logger.exception("process exception : %s", err)
            resp_message.error = repr(err)
            return TransactionMessage(resp_message.to_rpc()).to_bytes()

        else:
            logger.debug(resp_message)
            return TransactionMessage(resp_message.to_rpc()).to_bytes()

    def handle(self) -> None:
        """server handle"""

        print(" request from :", self.client_address)

        downloaded = io.BytesIO()

        try:
            while True:
                chunk = self.request.recv(BUFF_SIZE)
                downloaded.write(chunk)
                if len(chunk) < BUFF_SIZE:
                    break

            request_message = downloaded.getvalue()
            logger.debug("request_message : %s", request_message)
            results = self.handle_request(request_message)
            logger.debug("results : %s", results)
            self.request.sendall(results)

        except Exception:
            logger.exception("handling socket exception", exc_info=True)

        finally:
            downloaded.close()

    def finish(self):
        if TERMINATE:
            os.kill(os.getpid(), signal.SIGTERM)


def handle_exit(num, frame) -> None:
    sys.exit(0)


def main():

    signal.signal(signal.SIGTERM, handle_exit)

    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--port", help="socket port", type=int, default=8088)
    args = parser.parse_args()

    address = ("127.0.0.1", args.port)

    try:
        print(f">>> Server running at {address}.\n Press [CTRL+C] to stop.\n")
        server = socketserver.TCPServer(address, ServerHandler)
        server.serve_forever()

    except KeyboardInterrupt:
        print("KeyboardInterrupt (terminate server):\n Terminated.. .  . .")

    except OSError as err:
        print(repr(err))
        sys.exit(123)

    except Exception as err:
        logger.error(repr(err), exc_info=True)


if __name__ == "__main__":
    main()
