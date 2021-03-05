"""service module"""


from typing import List, Any, Dict, Optional
from jedi import Project as jedi_project
from . import completion, hover, document_formatting

from .completion import complete
from .hover import get_documentation
from .document_formatting import format_document

from .analyzer import lint


def to_rpc(results: Any, **kwargs) -> Optional[Dict[str, Any]]:
    """result to rpc

    Kwargs:
        source(str): required for document formatting

    Raises:
        NameError: required kwargs not initialized
    """

    if isinstance(results, completion.Completions):
        return completion.to_rpc(results)
    if isinstance(results, hover.Documentations):
        return hover.to_rpc(results)
    if isinstance(results, document_formatting.Changes):
        return document_formatting.to_rpc(results, source=kwargs["source"])

    return None


__all__ = [
    "completion",
    "complete",
    "hover",
    "get_documentation",
    "jedi_project",
    "document_formatting",
    "format_document",
    "lint",
    "to_rpc",
]
