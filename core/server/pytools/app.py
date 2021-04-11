"""main server"""

import argparse
import json
import logging
import os
import socketserver
import sys
import signal

from importlib.util import find_spec
from re import findall
from typing import Dict, List, Any, Optional, Tuple, Text

from api import rpc
from api import completion, hover, document_formatting, rename, analyzer


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
            super().__init__("params not found : %s" % str(err))
        else:
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
    def __init__(self, request, client_address, server):
        self.request = request
        self.client_address = client_address
        self.server = server

        self.commands = {}

        self.setup()
        try:
            self.handle()
        finally:
            self.finish()

    def setup(self):
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
        # self.commands[VALIDATE] = self.validate_source

    def ping(self, params: Any) -> Any:
        return params

    def exit(self, params: Any) -> Any:
        global TERMINATE
        TERMINATE = True
        return None

    def initialize(self, params: Any) -> Any:

        # features capable +++++++++++++++++++++++++++++++++++++++
        return {
            F_COMPLETION: bool(find_spec("jedi")),
            F_HOVER: bool(find_spec("jedi")),
            F_FORMATTING: bool(find_spec("black")),
            F_RENAME: bool(find_spec("rope")),
            F_DIAGNOSTIC: bool(find_spec("pylint")),
            # F_VALIDATE: bool(find_spec("pyflakes")),
        }

    def change_workspace(self, params: Any) -> Any:
        global WORKSPACE_DIRECTORY

        try:
            wparams = rpc.WorkspaceParams.from_rpc(params)
            WORKSPACE_DIRECTORY = wparams.uri
            results = {"workspace_directory": WORKSPACE_DIRECTORY}

        except (ValueError, KeyError) as err:
            raise InvalidParams(err) from err
        else:
            return results

    # def text_change(self, params: Any):
    #     """text change only accept full document changes"""

    #     global BUFFER

    #     try:
    #         BUFFER = params["newText"]
    #     except (ValueError, TypeError) as err:
    #         raise InvalidParams(err)
    #     else:
    #         return None

    # features function +++++++++++++++++++++++++++++++++++++++++
    def complete(self, params: Any) -> Any:
        try:
            tparams = rpc.TextDocumentPositionParams.from_rpc(params)
            path = tparams.uri
            line = tparams.location.line + 1  # jedi use 1 based index
            column = tparams.location.character

        except (ValueError, KeyError) as err:
            raise InvalidParams(err) from err

        try:
            project = (
                completion.Project(WORKSPACE_DIRECTORY) if WORKSPACE_DIRECTORY else None
            )
            completions_candidate = completion.complete(
                path, line=line, column=column, project=project
            )
            results = completion.to_rpc(completions_candidate)

        except Exception as err:
            raise InternalError(err) from err
        else:
            return results

    def hover(self, params: Any) -> Any:
        try:
            tparams = rpc.TextDocumentPositionParams.from_rpc(params)
            path = tparams.uri
            line = tparams.location.line + 1  # jedi use 1 based index
            column = tparams.location.character

        except (ValueError, KeyError) as err:
            raise InvalidParams(err) from err

        try:
            project = (
                hover.Project(WORKSPACE_DIRECTORY) if WORKSPACE_DIRECTORY else None
            )
            documentation_candidate = hover.get_documentation(
                path, line=line, column=column, project=project
            )
            results = hover.to_rpc(documentation_candidate)

        except Exception as err:
            raise InternalError(err) from err
        else:
            return results

    def formatting(self, params: Any) -> Any:
        try:
            uri = rpc.DocumentURI.from_rpc(params)
            src = uri

        except (ValueError, KeyError) as err:
            raise InvalidParams(err) from err

        try:
            format_result = document_formatting.format_document(src)
            results = document_formatting.to_rpc(format_result, source=src)
        except Exception as err:
            raise InternalError(err) from err
        else:
            return results

    def rename(self, params: Any) -> Any:
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

    def get_diagnostic(self, params: Any):
        try:
            uri = rpc.DocumentURI.from_rpc(params)
        except (ValueError, KeyError) as err:
            raise InvalidParams(err) from err

        try:
            diagnostic = analyzer.lint(path=uri)
            results = analyzer.to_rpc(diagnostic)
        except Exception as err:
            raise InternalError(err)
        else:
            return results

    # def validate_source(self, params: Any):
    #     try:
    #         uri = rpc.DocumentURI.from_rpc(params)
    #     except (ValueError, KeyError) as err:
    #         raise InvalidParams(err) from err

    #     try:
    #         diagnostic = analyzer.lint(path=uri, engine="pyflakes")
    #         results = analyzer.to_rpc(diagnostic)
    #     except Exception as err:
    #         raise InternalError(err)
    #     else:
    #         return results

    # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

    def run(self, method: str, params: Any):
        try:
            command = self.commands[method]
        except KeyError as err:
            raise MethodNotFound(err) from err
        else:
            return command(params)

    def handle_request(self, message: bytes) -> bytes:
        """handle request

        Returns:
            Tuple[result, next]
        """

        resp_message = rpc.ResponseMessage.builder("-1")

        try:
            # parsing requestcontent
            try:
                req_message = rpc.RequestMessage.from_rpc(get_rpc_content(message))
            except json.JSONDecodeError as err:
                raise InvalidRPCMessage(err) from err

            resp_message.id_ = req_message.id_

        except Exception as err:
            logger.debug("loading message error", exc_info=True)
            resp_message.error = repr(err)
            return create_rpc_content(resp_message.to_rpc())

        try:
            # processing

            results = self.run(req_message.method, req_message.params)
            resp_message.id_ = req_message.id_
            resp_message.results = results

        except Exception as err:
            logger.exception("process exception : %s", err)
            resp_message.error = repr(err)
            return create_rpc_content(resp_message.to_rpc())

        else:
            logger.debug(resp_message)
            return create_rpc_content(resp_message.to_rpc())

    def handle(self):
        """server handle"""

        print(" request from :", self.client_address)

        received = []

        try:
            while True:
                chunk = self.request.recv(BUFF_SIZE)
                received.append(chunk)
                if len(chunk) < BUFF_SIZE:
                    break

            request_message = b"".join(received)
            logger.debug("request_message : %s", request_message)
            results = self.handle_request(request_message)
            logger.debug("results : %s", results)
            self.request.sendall(results)

            if TERMINATE:
                os.kill(os.getpid(), signal.SIGTERM)

        except Exception as err:
            logger.exception("handling socket exception", exc_info=True)


def handle_exit(num, frame):
    sys.exit(0)


ADDRESS = ("127.0.0.1", 8088)


def main():

    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--port", help="socket port")
    args = parser.parse_args()

    global ADDRESS
    if args.port:
        ADDRESS = ("127.0.0.1", int(args.port))

    try:
        signal.signal(signal.SIGTERM, handle_exit)

        print(f">>> Server running at {ADDRESS}.\n Press [CTRL+C] to stop.\n")

        server = socketserver.TCPServer(ADDRESS, ServerHandler)
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
