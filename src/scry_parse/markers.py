"""Marker parsing for scry-spec v1.0.

Implements FR1-FR11. Recognizes:
- @scry.entry  (block marker — declarative knowledge entry)
- @scry.anchor (block marker — named code location)
- @scry.bind   (line or block marker — binding / cross-reference)

Comment prefix detection is inferred from the opening sentinel line.
Legacy @scry.doc and @scry.file are not recognized per v1.0.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import yaml


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class EntryMarker:
    id: str
    kind: str
    summary: str
    status: str
    weight: float | None  # None → default 0.5
    tags: list[str]
    rationale: str | None
    applies: str | None
    seeded_questions: list[str]
    depends_on: list[str]
    implements: str | None
    supersedes: str | None
    file: str
    span: tuple[int, int]  # (start_line, end_line) 1-indexed


@dataclass
class AnchorMarker:
    name: str   # the {local-id} from the sentinel
    description: str
    seeded_questions: list[str]
    file: str
    span: tuple[int, int]


@dataclass
class BindingMarker:
    local_id: str
    ref: str
    comment: str | None
    file: str
    offset: int              # line number (1-indexed) of the @scry.bind line
    span: tuple[int, int] | None  # (start, end) for block form; None for single-line


@dataclass
class ParseResult:
    entries: list[EntryMarker] = field(default_factory=list)
    anchors: list[AnchorMarker] = field(default_factory=list)
    bindings: list[BindingMarker] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Comment-prefix detection (inference-based, FR1 universality)
# ---------------------------------------------------------------------------

# Matches the portion of a line before the first YAML key
_KEY_RE = re.compile(r"^(.*?)([A-Za-z_][A-Za-z0-9_\-]*\s*:)")
# Valid comment-prefix characters: whitespace, #, /, *, -, >, ;
_PREFIX_VALID = re.compile(r"^[\s#/*\->;]*$")


def _infer_prefix(lines: list[str]) -> str:
    """Infer comment prefix from the first body line containing a YAML key.

    Algorithm (from scry reference implementation):
      1. Scan body lines for the first one whose non-key portion is purely
         whitespace + comment characters.
      2. That portion is the inferred prefix.

    This handles all comment styles — HTML, Python, TS/JS, SQL, Lisp, JSDoc,
    C-block, OCaml, Haskell, PowerShell — without enumeration.
    """
    for line in lines:
        m = _KEY_RE.match(line)
        if not m:
            continue
        candidate = m.group(1)
        if _PREFIX_VALID.match(candidate):
            return candidate
    return ""


# ---------------------------------------------------------------------------
# Regexes
# ---------------------------------------------------------------------------

# Matches the open sentinel for block markers (entry/anchor)
# Captures: (kind, rest_of_line)
_BLOCK_OPEN_RE = re.compile(r'@scry\.(entry|anchor)(?!\.end)\b(.*)')
# Matches the close sentinel
_BLOCK_CLOSE_RE = re.compile(r'@scry\.(entry|anchor)\.end\b')

# Bind markers
_BIND_OPEN_RE = re.compile(r'@scry\.bind(?!\.end)\b(.*)')
_BIND_CLOSE_RE = re.compile(r'@scry\.bind\.end\b')


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _strip_body_prefix(line: str, prefix: str) -> str:
    """Strip the comment prefix from a single body line."""
    if not prefix:
        return line
    if line.startswith(prefix):
        return line[len(prefix):]
    # Handle trailing-whitespace variant (e.g. "#\n" instead of "# \n")
    stripped = prefix.rstrip()
    if stripped and line.startswith(stripped):
        return line[len(stripped):].lstrip(" ")
    return line


def _clean_body(lines: list[str], body_strip_prefix: str | None = None) -> str:
    """Strip comment prefixes from all body lines and join.

    If body_strip_prefix is not given, the prefix is inferred from the first
    body line that looks like a YAML key — this makes block-comment styles
    (JSDoc, C /* */, OCaml (* *), Haskell {- -}, PowerShell <# #>, etc.)
    work without any enumeration.
    """
    prefix = body_strip_prefix if body_strip_prefix is not None else _infer_prefix(lines)
    cleaned = [_strip_body_prefix(ln, prefix) for ln in lines]
    return "".join(cleaned)


# Matches any @scry.* marker token line that might appear inside a block body
_SCRY_LINE_RE = re.compile(r'^\s*@scry\.\w+.*$', re.MULTILINE)


def _parse_yaml(text: str) -> dict[str, Any] | None:
    """Parse YAML safely; return None on failure.

    Strips any embedded @scry.* marker lines before parsing (they can appear
    inside block bodies due to FR3 positional exclusion — the parser doesn't
    index them, but they can still break YAML).
    """
    # Remove embedded @scry.* lines to avoid YAML parse errors
    cleaned = _SCRY_LINE_RE.sub("", text)
    try:
        data = yaml.safe_load(cleaned)
    except yaml.YAMLError:
        return None
    if not isinstance(data, dict):
        return None
    return data


def _coerce_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    if isinstance(value, str):
        return [value] if value.strip() else []
    return [str(value)]


def _coerce_str(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Block-span finder
# ---------------------------------------------------------------------------

def _find_block_spans(lines: list[str]) -> list[tuple[int, int, str, str]]:
    """Find all declarative block spans (entry, anchor).

    Returns list of (start_line_1idx, end_line_1idx, kind, sentinel_line).
    Lines are 1-indexed (matching span convention).
    """
    spans: list[tuple[int, int, str, str]] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        m = _BLOCK_OPEN_RE.search(line)
        if not m:
            i += 1
            continue
        kind = m.group(1)
        open_line_idx = i  # 0-indexed
        # Scan forward for matching close
        j = i + 1
        close_idx = None
        while j < len(lines):
            cm = _BLOCK_CLOSE_RE.search(lines[j])
            if cm and cm.group(1) == kind:
                close_idx = j
                break
            j += 1
        if close_idx is None:
            # Unterminated block — skip (FR: unterminated → 0 entries)
            i += 1
            continue
        # 1-indexed span
        spans.append((open_line_idx + 1, close_idx + 1, kind, line))
        i = close_idx + 1
    return spans


def _inside_any_span(
    line_1idx: int,
    spans: list[tuple[int, int, str, str]],
) -> bool:
    """Return True if line_1idx falls inside any declarative block span."""
    for start, end, _kind, _sentinel in spans:
        if start <= line_1idx <= end:
            return True
    return False


# ---------------------------------------------------------------------------
# Binding marker parser
# ---------------------------------------------------------------------------

def _parse_bind_content(
    rest: str, body_text: str
) -> tuple[str, str, str | None]:
    """Extract local_id, ref, and optional comment from bind marker content.

    Single-line form: `@scry.bind <local_id> <ref> [# comment]`
    Block form: open line has local_id + ref; body has comment.
    """
    # Try to parse from the rest (tokens after @scry.bind)
    tokens = rest.split()
    local_id = tokens[0] if len(tokens) >= 1 else ""
    ref = tokens[1] if len(tokens) >= 2 else ""

    # Comment: anything after the second token on the open line,
    # or the body text for block form
    if len(tokens) >= 3:
        comment: str | None = " ".join(tokens[2:]).lstrip("# ").strip()
    elif body_text:
        comment = body_text
    else:
        comment = None

    if comment == "":
        comment = None

    return local_id, ref, comment


def _expand_binding(
    local_id: str,
    ref: str,
    comment: str | None,
    file: str,
    offset: int,
    span: tuple[int, int] | None,
) -> list[BindingMarker]:
    """Expand multi-anchor refs (FR2).

    If ref is `{artifact}#{A},{B},{C}`, expand to N BindingMarker records.
    Range syntax `{A}-{B}` is treated as a single anchor name (no expansion).
    """
    # Check for comma-separated loose anchors in the fragment
    # Pattern: something~hash#ANCHOR1,ANCHOR2,...
    # or just: something#ANCHOR1,ANCHOR2,...
    comma_re = re.compile(r'^(.+)#([^,#]+(?:,[^,#]+)+)$')
    m = comma_re.match(ref)
    if m:
        base = m.group(1)
        anchors_str = m.group(2)
        anchors = [a.strip() for a in anchors_str.split(",")]
        # Only expand if these look like loose anchors (LOOSE_ANCHOR_REGEX)
        from scry_parse.consts import LOOSE_ANCHOR_REGEX
        if all(LOOSE_ANCHOR_REGEX.match(a) for a in anchors):
            return [
                BindingMarker(
                    local_id=local_id,
                    ref=f"{base}#{anchor}",
                    comment=comment,
                    file=file,
                    offset=offset,
                    span=span,
                )
                for anchor in anchors
            ]

    # Single binding
    return [BindingMarker(
        local_id=local_id,
        ref=ref,
        comment=comment,
        file=file,
        offset=offset,
        span=span,
    )]


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------

def parse_markers(
    content: str,
    language: str | None = None,
    file: str = "",
) -> ParseResult:
    """Parse all scry markers from file content.

    Args:
        content: The raw file content to parse.
        language: Optional language hint (currently unused; style is
                  inferred from the sentinel line).
        file: Optional file path to record in markers.

    Returns:
        ParseResult with entries, anchors, and bindings.
    """
    result = ParseResult()
    if "@scry." not in content:
        return result

    lines = content.splitlines(keepends=True)

    # First pass: find all declarative block spans
    block_spans = _find_block_spans(lines)

    # Second pass: parse each block
    for start_1idx, end_1idx, kind, sentinel_line in block_spans:
        # Body lines (between open and close, exclusive)
        body_lines = lines[start_1idx: end_1idx - 1]  # 0-indexed slice
        # Prefix inferred from body content — handles any comment style (FR1)
        body_text = _clean_body(body_lines)

        if kind == "anchor":
            _parse_anchor_block(
                sentinel_line, body_text, file,
                (start_1idx, end_1idx), result
            )
        elif kind == "entry":
            _parse_entry_block(
                body_text, file, (start_1idx, end_1idx), result
            )

    # Third pass: parse binding markers (prefix inferred per bind body)
    result.bindings = _parse_bindings_with_prefix(lines, block_spans, file)

    return result


def _parse_bindings_with_prefix(
    lines: list[str],
    block_spans: list[tuple[int, int, str, str]],
    file: str,
) -> list[BindingMarker]:
    """Parse bindings, detecting comment prefix per bind sentinel line."""
    result: list[BindingMarker] = []
    i = 0
    while i < len(lines):
        line_1idx = i + 1
        line = lines[i]

        m = _BIND_OPEN_RE.search(line)
        if not m:
            i += 1
            continue

        # FR3 exclusion
        if _inside_any_span(line_1idx, block_spans):
            i += 1
            continue

        rest = m.group(1).strip()

        # Forward-scan disambiguation (FR2)
        is_block = False
        close_line_idx = None
        j = i + 1
        while j < len(lines):
            if _BIND_CLOSE_RE.search(lines[j]):
                is_block = True
                close_line_idx = j
                break
            if _BIND_OPEN_RE.search(lines[j]):
                break
            j += 1

        if is_block and close_line_idx is not None:
            body_lines = lines[i + 1: close_line_idx]
            body_text = _clean_body(body_lines).strip()
            span: tuple[int, int] | None = (line_1idx, close_line_idx + 1)
            local_id, ref, comment = _parse_bind_content(rest, body_text)
            i = close_line_idx + 1
        else:
            span = None
            local_id, ref, comment = _parse_bind_content(rest, "")
            i += 1

        if not local_id or not ref:
            continue

        bindings = _expand_binding(local_id, ref, comment, file, line_1idx, span)
        result.extend(bindings)

    return result


def _parse_anchor_block(
    sentinel_line: str,
    body_text: str,
    file: str,
    span: tuple[int, int],
    result: ParseResult,
) -> None:
    """Parse an @scry.anchor block and append to result."""
    # Extract name from sentinel line: `@scry.anchor {name}`
    m = _BLOCK_OPEN_RE.search(sentinel_line)
    if not m:
        return
    rest = m.group(2).strip()
    # Name is the first token after the sentinel
    name_part = rest.split()[0] if rest.split() else ""
    if not name_part:
        return

    data = _parse_yaml(body_text) or {}
    description = _coerce_str(data.get("description")) or ""
    seeded_questions = _coerce_list(data.get("seeded_questions"))

    result.anchors.append(AnchorMarker(
        name=name_part,
        description=description,
        seeded_questions=seeded_questions,
        file=file,
        span=span,
    ))


def _parse_entry_block(
    body_text: str,
    file: str,
    span: tuple[int, int],
    result: ParseResult,
) -> None:
    """Parse a @scry.entry block and append to result."""
    data = _parse_yaml(body_text)
    if data is None:
        # Invalid YAML — fail gracefully, produce 0 entries
        return

    marker_id = _coerce_str(data.get("id"))
    if not marker_id:
        return

    kind = _coerce_str(data.get("kind")) or "internal"
    summary = _coerce_str(data.get("summary")) or ""
    status = _coerce_str(data.get("status")) or "draft"
    weight = _coerce_float(data.get("weight"))
    tags = _coerce_list(data.get("tags"))
    rationale = _coerce_str(data.get("rationale"))
    applies = _coerce_str(data.get("applies"))
    seeded_questions = _coerce_list(data.get("seeded_questions"))
    depends_on = _coerce_list(data.get("depends_on"))
    implements = _coerce_str(data.get("implements"))
    supersedes = _coerce_str(data.get("supersedes"))

    result.entries.append(EntryMarker(
        id=marker_id,
        kind=kind,
        summary=summary,
        status=status,
        weight=weight,
        tags=tags,
        rationale=rationale,
        applies=applies,
        seeded_questions=seeded_questions,
        depends_on=depends_on,
        implements=implements,
        supersedes=supersedes,
        file=file,
        span=span,
    ))
