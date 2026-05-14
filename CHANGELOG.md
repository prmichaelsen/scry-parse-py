# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
