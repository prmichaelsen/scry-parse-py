<!-- @scry.entry
id: design.scry-spec-fr15-code-block-exclusion~35c40589
kind: design
status: deprecated
weight: 0.4
tags: ["scope:scry-parse", "scope:scry-spec", "topic:phantom-markers", "topic:spec-proposal", "track:scry-parse-py", "topic:fr11.7", "fr11.7", "phantom-markers"]
summary: >
  RESOLVED. Spec proposal for code-context exclusion rule (originally labeled FR15, landed as FR11.7).
  PR #2 closed as superseded 2026-05-15T08:11Z — originator committed FR11.7 directly on main
  (commit 74c737c); spec advanced to v1.0.3 which includes FR11.7 and FR4/11.4 array enforcement.
  Implemented in scry-parse-py v1.0.4+, scry-parse-ts v1.0.5+. PR proposal body retained for
  historical reference only. Also: code-construct exclusion, inert-context, phantom anchors,
  fenced code blocks, inline code, FR11.7, PR #2, closed, superseded.
rationale: >
  Historical record of the FR11.7 proposal process. FR11.7 is now normative in scry-spec v1.0.3;
  this doc exists only as provenance. Do not treat "pending originator merge" as still-open work.
applies: "auditing FR11.7 history, understanding how code-block exclusion entered the spec, checking what happened to scry-spec PR #2"
seeded_questions:
  - "Does scry-spec address fenced code block exclusion?"
  - "Should markers in code examples be indexed?"
  - "How does scry-parse-py suppress phantom markers?"
  - "What FR covers code block exclusion in scry-spec?"
  - "Why do phantom anchors appear in production DB?"
  - "Was FR15 filed as a PR?"
  - "What happened to the FR15 proposal?"
  - "Is scry-spec PR #2 merged?"
  - "Was scry-spec PR #2 closed or merged?"
  - "What commit added FR11.7 to scry-spec?"
@scry.entry.end -->

# Spec proposal: FR15 → FR11.7 — Code-Context Exclusion Rule

**Target:** [scry-spec](https://github.com/prmichaelsen/scry-spec) `v1.0.md`  
**Status:** [PR #2](https://github.com/prmichaelsen/scry-spec/pull/2) — CLOSED as superseded 2026-05-15T08:11Z; FR11.7 landed directly on main (commit 74c737c), spec at v1.0.3  
**Spec number:** Originally proposed as FR15; landed as **FR11.7** in the spec  
**Motivation:** scry-parse v1.0.4 shipped this behavior; spec did not mandate it. PR #2 adds FR11.7 to v1.0.1.

---

> **Update 2026-05-15 (original):** PR #2 filed at commit `65e3852`. The requirement was added after §11.6 as §11.7
> (not as a standalone FR15), keeping the inert-context rules co-located. scry-parse-py v1.0.6 and
> scry-parse-ts v1.0.5+ both implement the behavior.
>
> **Update 2026-05-15T08:11Z (final):** PR #2 closed as superseded. Originator committed FR11.7 directly
> on main at commit 74c737c and advanced spec to v1.0.3. PR branch was rendered stale. No further action needed.
> This proposal document is historical record only.

---

---

## Problem

Documentation examples, test fixtures, and inline code spans routinely contain
`@scry.*` tokens as literal text, not as functional markers. Without an explicit
exclusion rule, conforming parsers index these phantom rows — producing `scry__anchor`
entries named `","` or `` "`" ``, and `scry__doc` rows from spec examples.

**Observed in production DB:**
- ~12 phantom doc rows from `markers.test.ts` fenced code block fixtures
- Orphaned anchors named `","`, `` "`" ``, `` "`," `` from scry-parse-ts test files
- `{ident}","` anchor from `mint.py` triple-quoted docstring

---

## Proposed requirement: FR15

### FR15: Code-Context Exclusion Rule

Parsers MUST treat the following regions as **inert** — `@scry.*` tokens within
them MUST NOT produce markers:

#### FR15.1 — Markdown/text fenced code blocks

A fenced code block begins with a line containing three or more backtick (`` ` ``) or
tilde (`~`) characters as the opening fence, and ends with a matching fence (same
character, same-or-greater count). Content between the opening and closing fence
lines (inclusive) is inert.

Complies with CommonMark §4.5 fenced code block rules.

#### FR15.2 — Inline code spans

A line where `@scry.` appears exclusively within backtick-delimited spans is inert.
If `@scry.` appears both inside and outside backtick spans on the same line, the
token(s) outside are NOT inert and MUST be processed normally.

#### FR15.3 — Language string literals (implementation-defined per language)

When a parser has language context (via file extension or explicit hint), it SHOULD
exclude `@scry.*` tokens inside multi-line string literals of that language.

**Rationale for SHOULD (not MUST):** Language-specific string detection requires
language awareness that pure text parsers may not have. FR15.1 and FR15.2 cover the
most common cases (Markdown documentation and inline code). Language string literal
exclusion is beneficial but not mandatory for conformance.

**Reference implementation (Python):** triple-quoted strings (`"""…"""`, `'''…'''`)
in `.py` files are inert.

---

## Interaction with existing FRs

- **FR3 (Positional Exclusion):** FR3 covers `@scry.bind` inside declarative marker
  spans. FR15 is broader — all marker types, any code-display context. They are
  complementary and non-overlapping.
- **FR11.6 (Binding Marker Discovery):** Add step 0 before step 1: "Skip the line
  if it falls within an inert region per FR15." Document the same for declarative
  marker discovery in FR11.1.

---

## Conformance

**Mandatory:** FR15.1 and FR15.2 — parsers MUST implement these to be conformant.  
**Optional:** FR15.3 — parsers SHOULD implement where language context is available.

---

## Reference implementation

scry-parse (Python) v1.0.4 — `_compute_inert_lines()` in `src/scry_parse/markers.py`.

Key behaviors:
- Pre-computes the full inert set in a single pass before marker extraction
- Outer loop in `_find_block_spans` skips inert lines when seeking open sentinels
- Inner close-sentinel scan also skips inert lines (avoid closing fence inside inert block)
- `_parse_bindings_with_prefix` skips inert lines before bind-sentinel check
- 12 regression tests cover all cases

---

## GitHub issue text

**Title:** FR15: Code-context exclusion rule (fenced code blocks, inline code spans)

**Body:**

Markers appearing inside fenced code blocks, inline code spans, and language string
literals should be excluded from indexing. Without this rule, documentation examples
and test fixtures produce phantom rows in `scry__anchor` and `scry__doc` tables.

**Observed phantom rows in production:**
- Anchors named `","`, `` "`" `` from scry-parse-ts test fixtures
- Doc rows from spec examples in `markers.test.ts`

**Proposed FR15 (see draft below):**

```
FR15.1 — Fenced code blocks: content inside ``` or ~~~ fences is inert (CommonMark §4.5)
FR15.2 — Inline code spans: lines where @scry. appears only in backtick spans are inert  
FR15.3 — Language string literals: SHOULD exclude per-language multi-line strings
```

Reference implementation: scry-parse v1.0.4 `_compute_inert_lines()`.

This matters for consistency across Python (scry-parse) and TypeScript (scry-parse-ts)
implementations — without a spec mandate, they will diverge.
