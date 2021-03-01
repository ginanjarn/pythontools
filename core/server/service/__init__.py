"""service module"""


from typing import List, Any, Dict, Optional
from jedi import Project as jedi_project
from core.server.service import completion, hover

from core.server.service.completion import complete
from core.server.service.hover import get_documentation

from core.server.service.document_formatting import format_document
from core.server.service.analyzer import lint


def to_rpc(resuls: List[Any]) -> Optional[Dict[str, Any]]:
    """result to rpc"""

    if isinstance(resuls, completion.Completions):
        return completion.to_rpc(resuls)
    if isinstance(resuls, hover.Documentations):
        return hover.to_rpc(resuls)
    return None


__all__ = [
    "completion",
    "complete",
    "hover",
    "get_documentation",
    "jedi_project",
    "format_document",
    "lint",
]
