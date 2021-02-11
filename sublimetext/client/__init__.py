"""client"""


from .remote import (
    run_server,
    ServerError,
    ServerOffline,
    ping,
    initialize,
    shutdown,
    change_workspace,
)
from .completion import fetch_completion
from .hover import fetch_documentation
from .document_format import format_code


__all__ = [
    "ping",
    "initialize",
    "ServerError",
    "ServerOffline",
    "shutdown",
    "run_server",
    "fetch_completion",
    "fetch_documentation",
    "format_code",
]
