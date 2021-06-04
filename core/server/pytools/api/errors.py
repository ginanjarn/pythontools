"""API errors"""


class InvalidRPCMessage(ValueError):
    """Invalid RPC Message"""

    def __init__(self, err):
        super().__init__("Invalid RPC Message : %s" % repr(err))


class InvalidInput(ValueError):
    """Input invalid"""


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
