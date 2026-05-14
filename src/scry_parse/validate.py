"""Validation for parsed scry markers per scry-spec v1.0."""
from __future__ import annotations

from dataclasses import dataclass

from scry_parse.consts import (
    ID_REGEX,
    ANCHOR_ID_REGEX,
    BASELINE_KINDS,
    BASELINE_STATUSES,
)
from scry_parse.markers import EntryMarker, AnchorMarker, BindingMarker


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str]
    warnings: list[str]


def validate_marker(marker: EntryMarker | AnchorMarker | BindingMarker) -> ValidationResult:
    """Validate a parsed marker against spec rules.

    Returns a ValidationResult with errors (spec violations) and warnings
    (non-standard but tolerated values).
    """
    if isinstance(marker, EntryMarker):
        return _validate_entry(marker)
    if isinstance(marker, AnchorMarker):
        return _validate_anchor(marker)
    if isinstance(marker, BindingMarker):
        return _validate_binding(marker)
    return ValidationResult(
        valid=False,
        errors=[f"Unknown marker type: {type(marker).__name__}"],
        warnings=[],
    )


def _validate_entry(marker: EntryMarker) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []

    # id must match ID_REGEX
    if not marker.id or not ID_REGEX.match(marker.id):
        errors.append(
            f"id {marker.id!r} does not match expected pattern "
            f"'<kind>.<name>~<8hexchars>' (got {marker.id!r})"
        )

    # kind must be non-empty; warn if not in BASELINE_KINDS
    if not marker.kind or not marker.kind.strip():
        errors.append("kind must be a non-empty string")
    elif marker.kind not in BASELINE_KINDS:
        warnings.append(
            f"kind {marker.kind!r} is not in the baseline kinds list; "
            f"expected one of: {', '.join(BASELINE_KINDS)}"
        )

    # summary must be non-empty
    if not marker.summary or not marker.summary.strip():
        errors.append("summary must be non-empty")

    # status must be non-empty; warn if not in BASELINE_STATUSES
    if not marker.status or not marker.status.strip():
        errors.append("status must be a non-empty string")
    elif marker.status not in BASELINE_STATUSES:
        warnings.append(
            f"status {marker.status!r} is not in the baseline statuses list; "
            f"expected one of: {', '.join(BASELINE_STATUSES)}"
        )

    valid = len(errors) == 0
    return ValidationResult(valid=valid, errors=errors, warnings=warnings)


def _validate_anchor(marker: AnchorMarker) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []

    # name must match ANCHOR_ID_REGEX
    if not marker.name or not ANCHOR_ID_REGEX.match(marker.name):
        errors.append(
            f"name {marker.name!r} does not match expected pattern "
            f"'<name>~<8hexchars>' (got {marker.name!r})"
        )

    # description must be non-empty
    if not marker.description or not marker.description.strip():
        errors.append("description must be non-empty")

    # seeded_questions must be declared (can be empty list)
    # It's a list type so always present; no additional check needed.

    valid = len(errors) == 0
    return ValidationResult(valid=valid, errors=errors, warnings=warnings)


def _validate_binding(marker: BindingMarker) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []

    # local_id must match ANCHOR_ID_REGEX
    if not marker.local_id or not ANCHOR_ID_REGEX.match(marker.local_id):
        errors.append(
            f"local_id {marker.local_id!r} does not match expected pattern "
            f"'<name>~<8hexchars>' (got {marker.local_id!r})"
        )

    # ref must be non-empty
    if not marker.ref or not marker.ref.strip():
        errors.append("ref must be non-empty")

    valid = len(errors) == 0
    return ValidationResult(valid=valid, errors=errors, warnings=warnings)
