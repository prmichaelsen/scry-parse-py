# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.9] - 2026-05-15

### Changed

- **docs: bump spec conformance claim to v1.0.5** — README spec version updated from v1.0.5
  to reflect actual conformance (FR11.6 from v1.0.4 landed in v1.0.8; FR4.A from v1.0.5
  is non-normative — no parser change required). No code or test changes.

---

## [1.0.8] - 2026-05-15

### Fixed

- **FR11.6 v1.0.4 — strip host-comment closers from single-line bind comment** — Single-line
  `@scry.bind` markers hosted inside HTML (`<!-- ... -->`) or C-style block (`/* ... */`)
  comments were leaking closing delimiters (` -->`, ` */`) into the `comment` field.
  Added `_strip_comment_closers` helper; applied after assembling trailing-content tokens.
  Matches scry-spec v1.0.4. Added Tests 23–24 (106 total).

---

## [1.0.7] - 2026-05-15

### Fixed

- **FR11.4 enforcement — `depends_on` scalar form now rejected** — `depends_on`
  was using `_coerce_list` (silently coercing scalar strings to single-element
  lists) while `implements` and `supersedes` correctly used `_strict_array`.
  Scalar `depends_on` now causes the entry to be rejected, consistent with FR11.4
  and the behavior of the other two relationship fields. Matches scry-parse-ts
  v1.0.7 which fixed the same discrepancy.
- Added `test_depends_on_scalar_form_rejected` (1 new test, 104 total).

---

## [1.0.6] - 2026-05-15

### Changed

- **FR11.4 enforcement — `implements` and `supersedes` must be arrays** — scalar
  string values for these fields now raise a `ValidationError` (error code
  `not_array`). The spec requires array form (`["id1", "id2"]`); singletons must
  use `["id"]`. `depends_on` was already enforced as array-only; this aligns
  `implements` and `supersedes` with the same rule.
- 4 new tests: `test_implements_array_form_ok`, `test_implements_scalar_form_rejected`,
  `test_supersedes_scalar_form_rejected`, `test_singleton_array_form`.

---

## [1.0.5] - 2026-05-15

### Fixed

- **Python single-line string literal exclusion** — a line where every `@scry.`
  token is inside a Python string literal (`"..."`, `'...'`, f-strings, b-strings)
  is now inert. Fixes phantom anchors from `mint.py`-style code:
  `"marker_open": f"<!-- @scry.anchor {ident}"` was producing phantom anchors
  named `{ident}","` in the production DB.
- Fix `__version__` in `__init__.py` (was left at `1.0.3` after v1.0.4 release).
- 2 additional regression tests: `test_python_string_literal_marker_ignored`,
  `test_python_real_comment_not_excluded_by_string_detection`.

---

## [1.0.4] - 2026-05-15

### Fixed

- **Phantom-marker suppression** — markers inside the following contexts are no
  longer indexed:
  - Markdown / text fenced code blocks (`` ``` `` and `~~~`, any language tag,
    CommonMark indent rules)
  - Inline backtick code spans (single, double, or triple backticks) on any
    single line
  - Python triple-quoted string literals (`"""…"""` and `'''…'''`, both
    single-line and multi-line; activated by `language='python'` hint or `.py`
    file extension)
- Root cause: the parser was scanning all lines for `@scry.*` tokens without
  regard for whether those lines were inside documentation examples, test
  fixtures, or language string literals. This produced phantom rows in the
  `scry__anchor` and `scry__doc` tables from test files and spec documentation.
- 12 regression tests added covering fenced blocks, inline code spans, Python
  triple-quoted string literals, and mixed real+phantom scenarios.

---

## [1.0.3] - 2026-05-14

### Added

- **`ParseResult.markers` convenience property** — returns all parsed markers in
  a single flat list (`[*entries, *anchors, *bindings]`). Added to support FR13/FR14
  test coverage (binding semantics and soft-reference validation). Callers that
  iterate `entries`, `anchors`, and `bindings` individually are unaffected.

---

## [1.0.2] - 2026-05-14

### Added

- `check_cycles(markers)` — new public API function implementing scry-spec FR12.
  Detects cycles in the `depends_on` directed graph across a collection of
  `EntryMarker` objects. Returns a list of human-readable error strings, one per
  cycle detected (e.g. `"cycle detected: design.a~... → design.b~... → design.a~..."`).
  Unresolved references (IDs not present in the provided markers) are silently
  skipped; non-entry markers (AnchorMarker, BindingMarker) are ignored.
- Fixed `__version__` drift: `__init__.py` now matches `pyproject.toml` (was 1.0.0, now
  auto-kept in sync with the published version).

## [1.0.1] - 2026-05-14

### Fixed

- Block-comment styles (JSDoc `/** */`, C `/* */`, OCaml `(* *)`, Haskell `{- -}`,
  PowerShell `<# #>`) now parse correctly. Previously, only line-comment styles
  (`#`, `//`, `--`, `;`, `<!-- -->`) were supported, which violated the spec's FR1
  universality claim.
- Comment-prefix detection now uses inference from the first YAML-key body line rather
  than a hardcoded `_COMMENT_STYLES` list. New comment styles work without parser changes.
- `@scry.bind` block form in JSDoc-style comments now correctly strips ` * ` continuation
  prefix from body lines.

## [1.0.0] - 2026-05-14

### Added

- Initial release: Python parser for scry-spec v1.0 marker format
- `parse_markers(content, language)` — parses EntryMarker, AnchorMarker, and BindingMarker from any host-language comment style
- `validate_marker(marker)` — validates parsed markers against spec rules, returns errors and warnings
- `mint_id(kind, name, content)` — generates spec-conformant marker IDs with deterministic (content-based) or random hashes
- `BASELINE_KINDS` and `BASELINE_STATUSES` constants per scry-spec v1.0
- Support for HTML/markdown, Python, TypeScript/JS, SQL, and Lisp comment styles
- FR3 positional exclusion: bind markers inside entry/anchor bodies are not indexed
- FR2 multi-anchor expansion: comma-separated loose anchors expand to N BindingMarker records
- Block form and single-line binding marker support
- 19 spec compliance tests plus additional edge case coverage
