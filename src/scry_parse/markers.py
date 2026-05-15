"""Marker parsing for scry-spec v1.0.

Implements FR1-FR14. Recognizes:
- @scry.entry  (block marker — declarative knowledge entry)
- @scry.anchor (block marker — named code location)
- @scry.bind   (line or block marker — binding / cross-reference)

Comment prefix detection uses YAML-key inference (FR1 universality).
Block-comment styles (JSDoc /** */, C /* */, OCaml (* *), Haskell {- -},
PowerShell <# #>, Ruby =begin/=end) work automatically — no enumeration needed.

Phantom-marker exclusion: markers inside fenced code blocks, inline backtick
code spans, and Python triple-quoted string literals are NOT indexed.
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
    implements: list[str]
    supersedes: list[str]
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

    @property
    def markers(self) -> list[EntryMarker | AnchorMarker | BindingMarker]:
        """All markers in parse order: entries + anchors + bindings."""
        return [*self.entries, *self.anchors, *self.bindings]


# ---------------------------------------------------------------------------
# Comment-prefix inference (FR1 universality)
# ---------------------------------------------------------------------------

# Matches the first YAML-key portion of a line:
#   group(1) = everything before the key (candidate comment prefix)
#   group(2) = the YAML key name + colon
_KEY_RE = re.compile(r"^(.*?)([A-Za-z_][A-Za-z0-9_\-]*\s*:)")

# Valid comment-prefix character set — whitespace + comment chars across languages.
# Includes ; for Lisp (;, ;;) and other common single- and block-comment chars.
_PREFIX_VALID = re.compile(r"^[\s#/*\->;]*$")


def _infer_prefix(lines: list[str]) -> str:
    """Infer the comment prefix from the first YAML-key body line.

    Algorithm (adapted from scry-mcp reference, comments.py):
      1. Scan body lines for the first one whose pre-key portion is purely
         whitespace + comment characters.
      2. That portion is the inferred prefix.
    Returns the prefix string, or "" if no inference is possible.

    Handles all comment styles without enumeration:
      - Line-comment: # (Python/shell), // (C/JS/TS), -- (SQL), ;; / ; (Lisp)
      - Block-comment body lines: " * " (JSDoc), "   " (indented C/OCaml/Haskell)
    """
    for line in lines:
        line_clean = line.rstrip("\r\n")
        m = _KEY_RE.match(line_clean)
        if not m:
            continue
        candidate = m.group(1)
        if _PREFIX_VALID.match(candidate):
            return candidate
    return ""


def _strip_body_prefix(line: str, prefix: str) -> str:
    """Strip a known comment prefix from a single body line."""
    if not prefix:
        return line
    if line.startswith(prefix):
        return line[len(prefix):]
    # Handle trailing-whitespace variant: e.g. "# " prefix but line is "#\n"
    stripped_prefix = prefix.rstrip()
    if stripped_prefix and line.startswith(stripped_prefix):
        return line[len(stripped_prefix):].lstrip(" ")
    return line


def _clean_body(lines: list[str]) -> str:
    """Infer comment prefix from body lines and strip it uniformly.

    Used for entry and anchor blocks. Works for all comment styles including
    block forms (JSDoc, C-block, OCaml, Haskell, PowerShell) via inference.
    """
    prefix = _infer_prefix(lines)
    if not prefix:
        return "".join(lines)
    out: list[str] = []
    for line in lines:
        if line.strip() == "":
            out.append(line)  # preserve blank lines as-is
        else:
            out.append(_strip_body_prefix(line, prefix))
    return "".join(out)


def _detect_bind_prefix(sentinel_line: str) -> str:
    """Extract the comment prefix from a @scry.bind sentinel line.

    Returns the text before '@scry.bind' if it consists only of valid
    comment characters, otherwise "".
    """
    idx = sentinel_line.find("@scry.bind")
    if idx < 0:
        return ""
    candidate = sentinel_line[:idx]
    if _PREFIX_VALID.match(candidate):
        return candidate
    return ""


def _clean_bind_body(lines: list[str], prefix: str) -> str:
    """Strip known comment prefix from binding body lines."""
    if not prefix:
        return "".join(lines)
    return "".join(_strip_body_prefix(ln, prefix) for ln in lines)


# ---------------------------------------------------------------------------
# Inert-line detection (phantom-marker suppression)
# ---------------------------------------------------------------------------

# Markdown fenced code block opener: up to 3 leading spaces + 3+ backticks or tildes.
# Optional info string (language tag) follows the fence characters.
_FENCE_OPEN_RE = re.compile(r'^( {0,3})(```+|~~~+)')


def _strip_inline_code(line: str) -> str:
    """Remove inline backtick code spans from a line, replacing with spaces.

    Handles any-length backtick runs (`, ``, ```).  An unclosed run is
    left in place so the caller doesn't misidentify the surrounding text.
    """
    result = list(line)
    i = 0
    length = len(line)
    while i < length:
        if line[i] != '`':
            i += 1
            continue
        # Count opening backticks
        j = i
        while j < length and line[j] == '`':
            j += 1
        tick_count = j - i
        # Search for matching closing run
        k = j
        closed = False
        while k < length:
            if line[k] == '`':
                m = k
                while m < length and line[m] == '`':
                    m += 1
                if m - k == tick_count:
                    # Replace entire span with spaces
                    for p in range(i, m):
                        result[p] = ' '
                    i = m
                    closed = True
                    break
                k = m
            else:
                k += 1
        if not closed:
            i = j  # skip past unclosed backtick run
    return ''.join(result)


def _scry_only_in_inline_code(line: str) -> bool:
    """Return True if every @scry. occurrence on the line is inside backtick spans."""
    if '@scry.' not in line:
        return False
    return '@scry.' not in _strip_inline_code(line)


def _strip_py_single_line_strings(line: str) -> str:
    """Remove content inside single-line Python string/f-string literals.

    Handles basic single-quoted and double-quoted strings with backslash escapes.
    Does not handle triple-quoted strings (those are handled by the multi-line
    pass in _compute_inert_lines).  The string prefix characters (f, b, r, etc.)
    are left in place; only the quoted content is removed.
    """
    result: list[str] = []
    i = 0
    n = len(line)
    while i < n:
        ch = line[i]
        if ch in ('"', "'"):
            # Do NOT consume the opening quote char (so it's absent from result);
            # skip past the closing quote.
            quote = ch
            i += 1
            while i < n:
                if line[i] == '\\':
                    i += 2  # skip escape sequence
                elif line[i] == quote:
                    i += 1  # skip closing quote
                    break
                else:
                    i += 1
            # String content is not appended
        else:
            result.append(ch)
            i += 1
    return ''.join(result)


def _scry_only_in_py_strings(line: str) -> bool:
    """Return True if every @scry. on the line is inside a Python string literal."""
    if '@scry.' not in line:
        return False
    return '@scry.' not in _strip_py_single_line_strings(line)


def _compute_inert_lines(
    lines: list[str],
    language: str | None = None,
    file: str = "",
) -> set[int]:
    """Return the set of 0-indexed line numbers that must not be scanned for markers.

    Excludes lines inside:
    - Markdown / any-file fenced code blocks (``` or ~~~, standard CommonMark rules)
    - Python triple-quoted strings (triggered by language='python' or .py extension)
    - Single lines where @scry. appears only within inline backtick spans
    """
    inert: set[int] = set()
    n = len(lines)
    is_python = (language == "python") or (
        isinstance(file, str) and file.endswith(".py")
    )

    # --- Pass 1: multi-line inert regions ---
    i = 0
    while i < n:
        raw = lines[i].rstrip('\r\n')
        found_block = False

        # Markdown fenced code block
        fence_m = _FENCE_OPEN_RE.match(raw)
        if fence_m:
            fence_char = fence_m.group(2)[0]  # '`' or '~'
            fence_min = len(fence_m.group(2))
            close_re = re.compile(
                rf'^ {{0,3}}{re.escape(fence_char)}{{{fence_min},}}\s*$'
            )
            inert.add(i)
            i += 1
            while i < n:
                ln = lines[i].rstrip('\r\n')
                inert.add(i)
                if close_re.match(ln):
                    i += 1
                    break
                i += 1
            found_block = True

        # Python triple-quoted strings
        elif is_python:
            for quote_str in ('"""', "'''"):
                open_idx = raw.find(quote_str)
                if open_idx < 0:
                    continue
                # Check whether the string closes on the same line
                close_idx = raw.find(quote_str, open_idx + 3)
                if close_idx >= 0:
                    # Single-line triple-quoted string: inert only if @scry. is inside
                    if '@scry.' in raw[open_idx + 3: close_idx]:
                        inert.add(i)
                    i += 1
                    found_block = True
                    break
                else:
                    # Multi-line triple-quoted string: mark until the closing delimiter
                    inert.add(i)
                    i += 1
                    while i < n:
                        ln = lines[i].rstrip('\r\n')
                        inert.add(i)
                        if quote_str in ln:
                            i += 1
                            break
                        i += 1
                    found_block = True
                    break

        if not found_block:
            i += 1

    # --- Pass 2: single-line exclusions ---
    # • For Python files: check whether @scry. appears only inside string literals.
    # • For all other files: check whether @scry. appears only inside inline backtick
    #   spans (common in markdown documentation and TypeScript test fixtures).
    for j, line in enumerate(lines):
        if j in inert or '@scry.' not in line:
            continue
        if is_python:
            if _scry_only_in_py_strings(line):
                inert.add(j)
        else:
            if _scry_only_in_inline_code(line):
                inert.add(j)

    return inert


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


def _strict_array(value: Any) -> tuple[list[str], bool]:
    """Return (list, ok). ok=False if a scalar string was provided (parse error per FR11.4)."""
    if value is None:
        return [], True
    if isinstance(value, list):
        return [str(v) for v in value], True
    # Scalar string or any other non-list type → hard parse error
    return [], False


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

def _find_block_spans(
    lines: list[str],
    inert: set[int] | None = None,
) -> list[tuple[int, int, str, str]]:
    """Find all declarative block spans (entry, anchor).

    Returns list of (start_line_1idx, end_line_1idx, kind, sentinel_line).
    Lines are 1-indexed (matching span convention).

    Lines in `inert` (0-indexed) are skipped when looking for open sentinels;
    they cannot start a valid marker block.
    """
    inert = inert or set()
    spans: list[tuple[int, int, str, str]] = []
    i = 0
    while i < len(lines):
        if i in inert:
            i += 1
            continue
        line = lines[i]
        m = _BLOCK_OPEN_RE.search(line)
        if not m:
            i += 1
            continue
        kind = m.group(1)
        open_line_idx = i  # 0-indexed
        # Scan forward for matching close (inert lines are scanned but cannot be the
        # close sentinel — a close inside a code block would be phantom content too)
        j = i + 1
        close_idx = None
        while j < len(lines):
            if j not in inert:
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

def _parse_bindings_with_prefix(
    lines: list[str],
    block_spans: list[tuple[int, int, str, str]],
    file: str,
    inert: set[int] | None = None,
) -> list[BindingMarker]:
    """Parse bindings, detecting comment prefix from each bind sentinel line."""
    inert = inert or set()
    result: list[BindingMarker] = []
    i = 0
    while i < len(lines):
        line_1idx = i + 1
        line = lines[i]

        # Skip lines inside code blocks / inline code / string literals
        if i in inert:
            i += 1
            continue

        m = _BIND_OPEN_RE.search(line)
        if not m:
            i += 1
            continue

        # FR3 exclusion
        if _inside_any_span(line_1idx, block_spans):
            i += 1
            continue

        # Detect comment prefix from sentinel line for body stripping
        body_strip_prefix = _detect_bind_prefix(line)
        rest = m.group(1).strip()

        # Forward-scan disambiguation (FR2):
        # Look for @scry.bind.end before the next @scry.bind
        is_block = False
        close_line_idx = None
        j = i + 1
        while j < len(lines):
            if _BIND_CLOSE_RE.search(lines[j]):
                is_block = True
                close_line_idx = j
                break
            if _BIND_OPEN_RE.search(lines[j]):
                # Next bind found before close → single-line form
                break
            j += 1

        if is_block and close_line_idx is not None:
            body_lines = lines[i + 1: close_line_idx]
            body_text = _clean_bind_body(body_lines, body_strip_prefix).strip()
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
                  inferred from YAML-key body lines per FR1).
        file: Optional file path to record in markers.

    Returns:
        ParseResult with entries, anchors, and bindings.
    """
    result = ParseResult()
    if "@scry." not in content:
        return result

    lines = content.splitlines(keepends=True)

    # Pre-compute inert line set: code blocks, inline code spans, string literals
    inert = _compute_inert_lines(lines, language=language, file=file)

    # First pass: find all declarative block spans (skips inert open sentinels)
    block_spans = _find_block_spans(lines, inert=inert)

    # Second pass: parse each block (comment prefix inferred per-block)
    for start_1idx, end_1idx, kind, sentinel_line in block_spans:
        # Body lines (between open and close, exclusive)
        body_lines = lines[start_1idx: end_1idx - 1]  # 0-indexed slice
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

    # Third pass: parse binding markers (per-sentinel prefix detection)
    result.bindings = _parse_bindings_with_prefix(lines, block_spans, file, inert=inert)

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
    implements, impl_ok = _strict_array(data.get("implements"))
    supersedes, sup_ok = _strict_array(data.get("supersedes"))
    if not impl_ok or not sup_ok:
        # Scalar relationship field is a hard parse error (FR11.4) — skip entry
        return

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
