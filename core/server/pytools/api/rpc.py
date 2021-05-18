"""rpc message interface"""


from enum import Enum
from typing import Dict, Any, Optional
from io import StringIO
import json

# fmt: off

# RPC KEYS
ID          = "id"
METHOD      = "method"
PARAMS      = "params"
RESULTS     = "results"
ERROR       = "error"

# ERROR
CODE        = "code"
MESSAGE     = "message"
DATA        = "data"

# ERROR CODE
class ErrorCode(Enum):
    INTERNAL_ERROR          = 90000
    TRANSACTION_ERROR       = 90001
    PARSE_MESSAGE_ERROR     = 90002
    INPUT_ERROR             = 90003
    METHOD_NOT_FOUND_ERROR  = 90004
    INVALID_PARAMS_ERROR    = 90005

# fmt: on


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


class ResponseError(dict):
    @property
    def code(self):
        return self[CODE]

    @property
    def message(self):
        return self[MESSAGE]

    @property
    def data(self):
        return self[DATA]

    @classmethod
    def builder(cls, code: ErrorCode, message: str, data: Optional[Any]=None):
        return cls({CODE: code.value, MESSAGE: message, DATA: data})

    @classmethod
    def from_rpc(cls, message: str) -> "ResponseMessage":
        return cls(json.loads(message))

    def to_rpc(self) -> str:
        return json.dumps(self)


Params = Dict[str, Any]


class DocumentURI(str):
    """uri formatted document path"""

    @classmethod
    def from_rpc(cls, params: Params) -> "DocumentURI":
        return cls(params["uri"])


class Position(dict):
    """cursor position at (line, column)"""

    @classmethod
    def builder(cls, line, character):
        holder = {}
        holder["line"] = line
        holder["character"] = character
        return cls(holder)

    @property
    def line(self) -> int:
        return self["line"]

    @property
    def character(self) -> int:
        return self["character"]

    @classmethod
    def from_rpc(cls, params: Params) -> "Position":
        return cls(params)


class TextDocumentPositionParams(dict):
    """cursor position at text document"""

    @classmethod
    def builder(cls, uri: DocumentURI, position: Position):
        holder = {}
        holder["uri"] = uri
        holder["location"] = position
        return cls(holder)

    @property
    def uri(self) -> DocumentURI:
        return self["uri"]

    @property
    def position(self) -> Position:
        return Position.from_rpc(self["location"])

    @classmethod
    def from_rpc(cls, params: Params) -> "TextDocumentPositionParams":
        return cls(params)


class WorkspaceParams(dict):
    """change workspace params"""

    @classmethod
    def builder(cls, uri: DocumentURI):
        holder = {}
        holder["uri"] = uri
        return cls(holder)

    @property
    def uri(self) -> DocumentURI:
        return self["uri"]

    @classmethod
    def from_rpc(cls, params: Params) -> "WorkspaceParams":
        return cls(params)


LABEL = "label"
TYPE = "type"


class CompletionItem(dict):
    """completion result"""

    @classmethod
    def builder(cls, label, type_, **kwargs):
        completion = {LABEL: label, TYPE: type_}
        if completion:
            completion.update(kwargs)
        return cls(completion)

    @property
    def label(self):
        return self[LABEL]

    @label.setter
    def label(self, value):
        self[LABEL] = value

    @property
    def type_(self):
        return self[TYPE]

    @type_.setter
    def type_(self, value):
        self[TYPE] = value


LINK = "link"


class Documentation(dict):
    """documentation result"""

    @classmethod
    def builder(cls, html_result, link):
        return cls({"html": html_result, LINK: link})

    @property
    def html_result(self):
        return self["html"]

    @html_result.setter
    def html_result(self, value):
        self["html"] = value

    @property
    def link(self):
        return self[LINK]

    @link.setter
    def link(self, value):
        self[LINK] = value


class DocumentLink(TextDocumentPositionParams):
    """link to document position"""


RANGE = "range"
START = "start"
END = "end"
LINE = "line"
CHARACTER = "character"
NEW_TEXT = "newText"


class Location(dict):
    """apply range

    >>> rg = rpc.Location.builder(rpc.Position.builder(0,0),rpc.Position.builder(10,0))
    >>> rg
    {'start': {'line': 0, 'character': 0}, 'end': {'line': 10, 'character': 0}}
    >>>

    """

    @classmethod
    def builder(cls, start: Position, end: Position):
        return cls({START: start, END: end})

    @property
    def start(self):
        return self[START]

    @start.setter
    def start(self, value):
        self[START] = value

    @property
    def end(self):
        return self[END]

    @end.setter
    def end(self, value):
        self[END] = value


class TextEdit(dict):
    """text edit change at range

    >>> te = rpc.TextEdit.builder(0,0,20,0,"hello world")
    >>> te
    {'range': {'start': {'line': 0, 'character': 0}, 'end': {'line': 20, 'character': 0}}, 'newText': 'hello world'}
    >>> json.dumps(te)
    '{"range": {"start": {"line": 0, "character": 0}, "end": {"line": 20, "character": 0}}, "newText": "hello world"}'
    >>>

    """

    HOLDER_KEY = "holder"

    @classmethod
    def builder(cls, start_line, start_character, end_line, end_character, new_text=""):
        range_ = Location.builder(
            Position.builder(start_line, start_character),
            Position.builder(end_line, end_character),
        )
        return cls({RANGE: range_, NEW_TEXT: new_text})

    @classmethod
    def from_rpc(cls, params):
        start = Position.from_rpc(params[START])
        end = Position.from_rpc(params[END])
        new_text = params[NEW_TEXT]
        range_ = Location.builder(start, end)
        return cls({RANGE: range_, NEW_TEXT: new_text})

    @property
    def new_text(self):
        return self[NEW_TEXT]

    @new_text.setter
    def new_text(self, value):
        self[NEW_TEXT] = value

    @property
    def start(self) -> Position:
        return self[START]

    @property
    def end(self) -> Position:
        return self[END]

    @property
    def _holder(self):
        return self[TextEdit.HOLDER_KEY]

    def accumulate_new_text(self, new_text):
        if TextEdit.HOLDER_KEY in self:
            self[TextEdit.HOLDER_KEY].write(f"\n{new_text}")
        else:
            text = StringIO()
            text.write(new_text)
            self[TextEdit.HOLDER_KEY] = text

    def build_new_text(self):
        if TextEdit.HOLDER_KEY not in self:
            raise ValueError("nothing builded")

        self[NEW_TEXT] = self[TextEdit.HOLDER_KEY].getvalue()
        self[TextEdit.HOLDER_KEY].close()
        del self[TextEdit.HOLDER_KEY]
