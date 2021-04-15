"""client"""


from .remote import (
    run_server,
    ServerError,
    ServerOffline,
    PortInUse,
    ping,
    initialize,
    shutdown,
    change_workspace,
)
from .completion import fetch_completion
from .hover import fetch_documentation
from .document_format import format_code
from .analyzer import get_diagnostic
from .rename import rename


__all__ = [
    "ping",
    "initialize",
    "ServerError",
    "ServerOffline",
    "PortInUse",
    "shutdown",
    "run_server",
    "fetch_completion",
    "fetch_documentation",
    "format_code",
    "get_diagnostic",
    "rename",
]
