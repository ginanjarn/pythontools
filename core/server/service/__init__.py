"""service module"""


from typing import List, Any, Dict, Optional
from jedi import Project as jedi_project
from . import completion, hover, document_formatting, rename

from .completion import complete, Completions
from .hover import get_documentation, Documentations
from .document_formatting import format_document, FormattingChanges
from .rename import rename_attribute, RenameChanges

from .analyzer import lint


def to_rpc(results: Any, **kwargs) -> Optional[Dict[str, Any]]:
    """result to rpc

    Kwargs:
        source(str): required for document formatting

    Raises:
        NameError: required kwargs not initialized
    """

    if isinstance(results, Completions):
        return completion.to_rpc(results)
    if isinstance(results, Documentations):
        return hover.to_rpc(results)
    if isinstance(results, FormattingChanges):
        return document_formatting.to_rpc(results, source=kwargs["source"])
    if isinstance(results, RenameChanges):
        return rename.to_rpc(results)

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
    "rename",
    "to_rpc",
]
