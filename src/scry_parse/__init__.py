"""scry-parse: Python parser for scry-spec v1.0 markers.

Public API:
    parse_markers(content, language=None, file="") -> ParseResult
    validate_marker(marker) -> ValidationResult
    check_cycles(markers) -> list[str]
    mint_id(kind, name, content=None) -> str
    BASELINE_KINDS
    BASELINE_STATUSES

Dataclasses:
    EntryMarker
    AnchorMarker
    BindingMarker
    ParseResult
    ValidationResult
"""

from scry_parse.markers import (
    parse_markers,
    EntryMarker,
    AnchorMarker,
    BindingMarker,
    ParseResult,
)
from scry_parse.validate import validate_marker, check_cycles, ValidationResult
from scry_parse.mint import mint_id
from scry_parse.consts import BASELINE_KINDS, BASELINE_STATUSES

__all__ = [
    "parse_markers",
    "EntryMarker",
    "AnchorMarker",
    "BindingMarker",
    "ParseResult",
    "validate_marker",
    "check_cycles",
    "ValidationResult",
    "mint_id",
    "BASELINE_KINDS",
    "BASELINE_STATUSES",
]

__version__ = "1.0.7"
