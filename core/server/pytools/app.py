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
from typing import Any, Tuple, Dict, Iterator

from api import rpc, errors
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
    def _generate_header_item(
        headers: Dict[str, str], encoding: str = "ascii"
    ) -> Iterator[str]:

        for key, value in headers.items():
            yield f"{key}: {value}".encode(encoding)

    def to_bytes(self) -> bytes:
        """generate encoded message"""

        merged_headers = HEADER_ITEMS_SEPARATOR.join(
            self._generate_header_item(self._headers)
        )
        return BODY_SEPARATOR.join([merged_headers, self._content_encoded])

    @staticmethod
    def _parse_header(header: bytes, encoding: str = "ascii") -> Dict[str, str]:
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

        self.commands = {
            PING: self.ping,
            EXIT: self.exit,
            INITIALIZE: self.initialize,
            CHANGE_WORKPACE: self.change_workspace,
            # features map ++++++++++++++++++++++++++++++++++++++++++
            COMPLETION: self.complete,
            HOVER: self.hover,
            FORMATTING: self.formatting,
            RENAME: self.rename,
            DIAGNOSTIC: self.get_diagnostic,
            VALIDATE: self.validate_source,
        }

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
        }

    def change_workspace(self, params: rpc.Params) -> Any:
        global WORKSPACE_DIRECTORY

        try:
            wparams = rpc.WorkspaceParams.from_rpc(params)
            WORKSPACE_DIRECTORY = wparams.uri
            results = {"workspace_directory": WORKSPACE_DIRECTORY}

        except (ValueError, KeyError) as err:
            raise errors.InvalidParams(err) from None
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
            raise errors.InvalidParams(err) from None

        project = (
            completion.Project(WORKSPACE_DIRECTORY) if WORKSPACE_DIRECTORY else None
        )

        cmpl = completion.Completion(path, line=line, column=column, project=project)
        return cmpl.to_rpc()

    def hover(self, params: rpc.Params) -> Any:
        try:
            tparams = rpc.TextDocumentPositionParams.from_rpc(params)
            path = tparams.uri
            line = tparams.position.line + 1  # jedi use 1 based index
            column = tparams.position.character

        except (ValueError, KeyError) as err:
            raise errors.InvalidParams(err) from None

        project = hover.Project(WORKSPACE_DIRECTORY) if WORKSPACE_DIRECTORY else None

        doc = hover.Documentation(path, line=line, column=column, project=project)
        return doc.to_rpc()

    def formatting(self, params: rpc.Params) -> Any:
        try:
            uri = rpc.DocumentURI.from_rpc(params)
            src = uri

        except (ValueError, KeyError) as err:
            raise errors.InvalidParams(err) from None

        formatted = document_formatting.DocumentFormatting(src)
        return formatted.to_rpc()

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
            raise errors.InvalidParams(err) from None

        changes = rename.Rename(project, resource, offset, new_name)
        return changes.to_rpc()

    def get_diagnostic(self, params: rpc.Params) -> Any:
        try:
            uri = rpc.DocumentURI.from_rpc(params)
        except (ValueError, KeyError) as err:
            raise errors.InvalidParams(err) from None

        lint = analyzer.PyLint(uri)
        return lint.to_rpc()

    def validate_source(self, params: rpc.Params) -> Any:
        try:
            uri = rpc.DocumentURI.from_rpc(params)
        except (ValueError, KeyError) as err:
            raise errors.InvalidParams(err) from None

        lint = analyzer.PyFlakes(uri)
        return lint.to_rpc()

    # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

    def run(self, method: str, params: rpc.Params) -> Any:
        try:
            command = self.commands[method]
        except KeyError as err:
            raise errors.MethodNotFound(err) from err
        else:
            return command(params)

    def handle_request(self, message: bytes) -> bytes:
        """handle request"""

        response_message = rpc.ResponseMessage.builder()

        try:
            # parsing requestcontent
            try:
                request_message = rpc.RequestMessage.from_rpc(
                    TransactionMessage.from_bytes(message).content
                )

            except json.JSONDecodeError as err:
                raise errors.InvalidRPCMessage(err) from err

            response_message.id_ = request_message.id_

        except Exception as err:
            logger.debug("loading message error", exc_info=True)
            response_message.error = repr(err)
            return TransactionMessage(response_message.to_rpc()).to_bytes()

        try:
            # processing

            results = self.run(request_message.method, request_message.params)
            response_message.id_ = request_message.id_
            response_message.results = results

        except errors.MethodNotFound as err:
            logger.debug("invalid method error : %s", err)
            response_message.error = rpc.ResponseError.builder(
                rpc.ErrorCode.METHOD_NOT_FOUND_ERROR, message=str(err)
            )
            return TransactionMessage(response_message.to_rpc()).to_bytes()

        except errors.InvalidParams as err:
            logger.debug("invalid params error : %s", err)
            response_message.error = rpc.ResponseError.builder(
                rpc.ErrorCode.INVALID_PARAMS_ERROR, message=str(err)
            )
            return TransactionMessage(response_message.to_rpc()).to_bytes()

        except errors.InvalidInput as err:
            logger.debug("invalid input error : %s", err)
            response_message.error = rpc.ResponseError.builder(
                rpc.ErrorCode.INPUT_ERROR, message=str(err)
            )
            return TransactionMessage(response_message.to_rpc()).to_bytes()

        except Exception as err:
            logger.exception("process exception : %s", err)
            response_message.error = rpc.ResponseError.builder(
                rpc.ErrorCode.INTERNAL_ERROR, message=repr(err)
            )
            return TransactionMessage(response_message.to_rpc()).to_bytes()

        else:
            logger.debug(response_message)
            return TransactionMessage(response_message.to_rpc()).to_bytes()

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
