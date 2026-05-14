"""scry-parse spec compliance tests (Tests 1-19 + extras).

Tests cover FR1-FR11 parser rules for scry-spec v1.0.
"""
from __future__ import annotations

import pytest

from scry_parse import (
    parse_markers,
    validate_marker,
    mint_id,
    EntryMarker,
    AnchorMarker,
    BindingMarker,
    ParseResult,
    ValidationResult,
    BASELINE_KINDS,
    BASELINE_STATUSES,
)
from scry_parse.consts import ID_REGEX, ANCHOR_ID_REGEX, LOOSE_ANCHOR_REGEX


# ---------------------------------------------------------------------------
# Fixtures / shared content strings
# ---------------------------------------------------------------------------

ENTRY_MARKDOWN = """\
<!-- @scry.entry
id: design.auth-flow~a1b2c3d4
kind: design
summary: >
  JWT auth middleware, token validation, refresh flow
status: active
weight: 0.85
tags: ["scope:auth", "topic:security"]
rationale: >
  Missing this causes auth bypass bugs
applies: modifying auth, adding protected endpoints
seeded_questions:
  - How does token refresh work?
@scry.entry.end -->
"""

ANCHOR_MARKDOWN = """\
<!-- @scry.anchor auth-check~f1e2d3c4
description: >
  JWT validation point for protected routes
seeded_questions:
  - What happens if token is expired?
@scry.anchor.end -->
"""


# ---------------------------------------------------------------------------
# Test 1: Valid entry marker (markdown form)
# ---------------------------------------------------------------------------

def test_1_valid_entry_marker_markdown():
    result = parse_markers(ENTRY_MARKDOWN)
    assert len(result.entries) == 1
    e = result.entries[0]
    assert e.id == "design.auth-flow~a1b2c3d4"
    assert e.kind == "design"
    assert "JWT auth middleware" in e.summary
    assert e.status == "active"
    assert e.weight == 0.85
    assert "scope:auth" in e.tags
    assert "topic:security" in e.tags
    assert "auth bypass" in e.rationale
    assert "modifying auth" in e.applies
    assert any("token refresh" in q for q in e.seeded_questions)
    assert len(result.anchors) == 0
    assert len(result.bindings) == 0


# ---------------------------------------------------------------------------
# Test 2: Valid anchor marker
# ---------------------------------------------------------------------------

def test_2_valid_anchor_marker():
    result = parse_markers(ANCHOR_MARKDOWN)
    assert len(result.anchors) == 1
    a = result.anchors[0]
    assert a.name == "auth-check~f1e2d3c4"
    assert "JWT validation point" in a.description
    assert any("expired" in q for q in a.seeded_questions)
    assert len(result.entries) == 0
    assert len(result.bindings) == 0


# ---------------------------------------------------------------------------
# Test 3: Two bind markers (single-line form)
# ---------------------------------------------------------------------------

def test_3_two_bind_markers():
    content = """\
# @scry.bind validate-jwt~a1b2c3d4 spec.auth~xyz89012#FR3
# @scry.bind jwt-expiry~b2c3d4e5 spec.auth~xyz89012#UT1
"""
    result = parse_markers(content)
    assert len(result.bindings) == 2
    ids = {b.local_id for b in result.bindings}
    assert "validate-jwt~a1b2c3d4" in ids
    assert "jwt-expiry~b2c3d4e5" in ids


# ---------------------------------------------------------------------------
# Test 4: Multiple entries in one file
# ---------------------------------------------------------------------------

def test_4_multiple_entries_in_one_file():
    content = """\
<!-- @scry.entry
id: design.auth~a1b2c3d4
kind: design
summary: Auth system
status: active
weight: 0.9
tags: []
rationale: >
  Core auth
applies: auth work
seeded_questions: []
@scry.entry.end -->

<!-- @scry.entry
id: spec.login~b2c3d4e5
kind: spec
summary: Login spec
status: draft
weight: 0.7
tags: []
rationale: >
  Spec needed
applies: login
seeded_questions: []
@scry.entry.end -->
"""
    result = parse_markers(content)
    assert len(result.entries) == 2
    ids = {e.id for e in result.entries}
    assert "design.auth~a1b2c3d4" in ids
    assert "spec.login~b2c3d4e5" in ids


# ---------------------------------------------------------------------------
# Test 5: FR3 exclusion — bind inside entry body not indexed
# ---------------------------------------------------------------------------

def test_5_fr3_bind_inside_entry_excluded():
    # FR3: a @scry.bind marker whose line falls within a block marker span must not be indexed.
    # Simulate a Python-style entry block that contains a bind line in the body.
    content = """\
# @scry.entry
# id: design.foo~a1b2c3d4
# kind: design
# summary: Example with bind inside body
# status: active
# weight: 0.5
# tags: []
# rationale: >
#   Test FR3
# applies: testing
# seeded_questions: []
# @scry.bind validate-jwt~a1b2c3d4 spec.auth~xyz89012#FR3
# @scry.entry.end
"""
    result = parse_markers(content)
    # The bind inside the entry body must NOT be indexed
    assert len(result.bindings) == 0
    # The entry should still be parsed
    assert len(result.entries) == 1


# ---------------------------------------------------------------------------
# Test 6: Unterminated block → 0 entries
# ---------------------------------------------------------------------------

def test_6_unterminated_block_produces_zero_entries():
    content = """\
<!-- @scry.entry
id: design.orphan~a1b2c3d4
kind: design
summary: This block is never closed
status: active
weight: 0.5
tags: []
"""
    result = parse_markers(content)
    assert len(result.entries) == 0


# ---------------------------------------------------------------------------
# Test 7: Unknown kind preserved as-is
# ---------------------------------------------------------------------------

def test_7_unknown_kind_preserved_as_is():
    content = """\
<!-- @scry.entry
id: design.thing~a1b2c3d4
kind: customkind
summary: Something custom
status: active
weight: 0.5
tags: []
rationale: >
  Custom kind test
applies: testing
seeded_questions: []
@scry.entry.end -->
"""
    result = parse_markers(content)
    assert len(result.entries) == 1
    # Kind is preserved as-is (not mapped to "internal")
    assert result.entries[0].kind == "customkind"


# ---------------------------------------------------------------------------
# Test 8: Invalid YAML → parse fails gracefully
# ---------------------------------------------------------------------------

def test_8_invalid_yaml_parse_fails_gracefully():
    content = """\
<!-- @scry.entry
id: design.broken~a1b2c3d4
kind: design
summary: : : invalid yaml :::
  bad: [unclosed
status: active
@scry.entry.end -->
"""
    result = parse_markers(content)
    # Should not raise; should return 0 entries
    assert isinstance(result, ParseResult)
    assert len(result.entries) == 0


# ---------------------------------------------------------------------------
# Test 9: Cross-kind bindings
# ---------------------------------------------------------------------------

def test_9_cross_kind_bindings():
    content = """\
# @scry.bind validate-jwt~a1b2c3d4 spec.auth~xyz89012#FR3
# @scry.bind jwt-test~b2c3d4e5 spec.auth~xyz89012#UT1
"""
    result = parse_markers(content)
    assert len(result.bindings) == 2
    refs = {b.ref for b in result.bindings}
    assert "spec.auth~xyz89012#FR3" in refs
    assert "spec.auth~xyz89012#UT1" in refs


# ---------------------------------------------------------------------------
# Test 10: Artifact-level binding (no anchor in ref)
# ---------------------------------------------------------------------------

def test_10_artifact_level_binding():
    content = "// @scry.bind my-impl~a1b2c3d4 design.auth-flow~a1b2c3d4\n"
    result = parse_markers(content)
    assert len(result.bindings) == 1
    b = result.bindings[0]
    assert b.local_id == "my-impl~a1b2c3d4"
    assert b.ref == "design.auth-flow~a1b2c3d4"


# ---------------------------------------------------------------------------
# Test 11: Multi-anchor expansion (3 records from comma-separated)
# ---------------------------------------------------------------------------

def test_11_multi_anchor_expansion():
    content = "# @scry.bind impl-auth~a1b2c3d4 spec.auth~xyz89012#FR1,FR2,FR3\n"
    result = parse_markers(content)
    assert len(result.bindings) == 3
    refs = {b.ref for b in result.bindings}
    assert "spec.auth~xyz89012#FR1" in refs
    assert "spec.auth~xyz89012#FR2" in refs
    assert "spec.auth~xyz89012#FR3" in refs
    # All share the same local_id
    assert all(b.local_id == "impl-auth~a1b2c3d4" for b in result.bindings)


# ---------------------------------------------------------------------------
# Test 12: Range syntax treated as single anchor name (no expansion)
# ---------------------------------------------------------------------------

def test_12_range_syntax_no_expansion():
    content = "# @scry.bind impl-range~a1b2c3d4 spec.auth~xyz89012#FR1-FR5\n"
    result = parse_markers(content)
    # Range "FR1-FR5" is not comma-separated → treated as single anchor name
    assert len(result.bindings) == 1
    assert result.bindings[0].ref == "spec.auth~xyz89012#FR1-FR5"


# ---------------------------------------------------------------------------
# Test 13: Binding with comment (single-line, inline)
# ---------------------------------------------------------------------------

def test_13_binding_with_comment():
    content = "# @scry.bind impl-auth~a1b2c3d4 spec.auth~xyz89012#FR3 # validates JWT header\n"
    result = parse_markers(content)
    assert len(result.bindings) == 1
    b = result.bindings[0]
    assert b.local_id == "impl-auth~a1b2c3d4"
    assert b.ref == "spec.auth~xyz89012#FR3"
    assert b.comment is not None
    assert "validates JWT header" in b.comment


# ---------------------------------------------------------------------------
# Test 14: Strict anchor reference (no dot in ref before ~)
# ---------------------------------------------------------------------------

def test_14_strict_anchor_reference():
    # ref with no dot before ~ → strict mode (anchor-id style)
    content = "# @scry.bind my-code~a1b2c3d4 auth-check~f1e2d3c4\n"
    result = parse_markers(content)
    assert len(result.bindings) == 1
    b = result.bindings[0]
    assert b.ref == "auth-check~f1e2d3c4"
    # No dot in ref before ~ → strict mode
    assert "." not in b.ref.split("~")[0]


# ---------------------------------------------------------------------------
# Test 16: Block form binding with multi-line comment
# ---------------------------------------------------------------------------

def test_16_block_form_binding_multiline_comment():
    content = """\
# @scry.bind impl-auth~a1b2c3d4 spec.auth~xyz89012#FR3
# This implements the JWT validation
# as described in FR3 of the auth spec.
# @scry.bind.end
"""
    result = parse_markers(content)
    assert len(result.bindings) == 1
    b = result.bindings[0]
    assert b.local_id == "impl-auth~a1b2c3d4"
    assert b.ref == "spec.auth~xyz89012#FR3"
    assert b.comment is not None
    assert "JWT validation" in b.comment
    assert b.span is not None


# ---------------------------------------------------------------------------
# Test 17: Block form vs single-line equivalence
# ---------------------------------------------------------------------------

def test_17_block_vs_single_line_equivalence():
    single_line = "# @scry.bind my-impl~a1b2c3d4 spec.auth~xyz89012#FR1\n"
    block_form = """\
# @scry.bind my-impl~a1b2c3d4 spec.auth~xyz89012#FR1
# @scry.bind.end
"""
    r1 = parse_markers(single_line)
    r2 = parse_markers(block_form)
    assert len(r1.bindings) == 1
    assert len(r2.bindings) == 1
    b1 = r1.bindings[0]
    b2 = r2.bindings[0]
    assert b1.local_id == b2.local_id
    assert b1.ref == b2.ref
    # single-line has no span; block form has a span
    assert b1.span is None
    assert b2.span is not None


# ---------------------------------------------------------------------------
# Test 18: No block (single-line, no comment)
# ---------------------------------------------------------------------------

def test_18_single_line_no_comment():
    content = "# @scry.bind impl-x~a1b2c3d4 spec.x~12345678\n"
    result = parse_markers(content)
    assert len(result.bindings) == 1
    b = result.bindings[0]
    assert b.span is None
    assert b.comment is None


# ---------------------------------------------------------------------------
# Test 19: Mixed inline + block (error/warning) — parser must not crash
# ---------------------------------------------------------------------------

def test_19_mixed_inline_and_block_no_crash():
    # A file with both single-line and block form bindings
    content = """\
# @scry.bind impl-a~a1b2c3d4 spec.auth~xyz89012#FR1
# @scry.bind impl-b~b2c3d4e5 spec.auth~xyz89012#FR2
# This is a block comment.
# @scry.bind.end
"""
    # Parser should handle this without crashing.
    # impl-a is single-line (next line is @scry.bind, not @scry.bind.end).
    # impl-b is a block form.
    result = parse_markers(content)
    assert isinstance(result, ParseResult)
    ids = {b.local_id for b in result.bindings}
    assert "impl-a~a1b2c3d4" in ids
    assert "impl-b~b2c3d4e5" in ids


# ---------------------------------------------------------------------------
# Python-style markers (# comment prefix)
# ---------------------------------------------------------------------------

def test_python_style_entry_marker():
    content = """\
# @scry.entry
# id: design.auth~a1b2c3d4
# kind: design
# summary: Python-style entry
# status: active
# weight: 0.5
# tags: []
# rationale: >
#   Testing Python style
# applies: testing
# seeded_questions: []
# @scry.entry.end
"""
    result = parse_markers(content)
    assert len(result.entries) == 1
    e = result.entries[0]
    assert e.id == "design.auth~a1b2c3d4"
    assert e.kind == "design"
    assert e.status == "active"


def test_python_style_anchor_marker():
    content = """\
# @scry.anchor auth-point~f1e2d3c4
# description: Main auth entry point
# seeded_questions:
#   - How is auth done?
# @scry.anchor.end
"""
    result = parse_markers(content)
    assert len(result.anchors) == 1
    a = result.anchors[0]
    assert a.name == "auth-point~f1e2d3c4"
    assert "auth entry point" in a.description


# ---------------------------------------------------------------------------
# TypeScript-style markers (// comment prefix)
# ---------------------------------------------------------------------------

def test_typescript_style_entry_marker():
    content = """\
// @scry.entry
// id: code.middleware~a1b2c3d4
// kind: code
// summary: TS-style entry
// status: draft
// weight: 0.4
// tags: []
// rationale: >
//   TypeScript test
// applies: ts work
// seeded_questions: []
// @scry.entry.end
"""
    result = parse_markers(content)
    assert len(result.entries) == 1
    e = result.entries[0]
    assert e.id == "code.middleware~a1b2c3d4"
    assert e.kind == "code"


def test_typescript_style_bind_marker():
    content = "// @scry.bind my-func~a1b2c3d4 spec.api~12345678#FR1\n"
    result = parse_markers(content)
    assert len(result.bindings) == 1
    assert result.bindings[0].ref == "spec.api~12345678#FR1"


# ---------------------------------------------------------------------------
# mint_id tests
# ---------------------------------------------------------------------------

def test_mint_id_with_content_is_deterministic():
    content = "some deterministic content"
    id1 = mint_id("design", "auth-flow", content)
    id2 = mint_id("design", "auth-flow", content)
    assert id1 == id2
    assert id1.startswith("design.auth-flow~")
    # Hash portion is 8 hex chars
    hash_part = id1.split("~")[1]
    assert len(hash_part) == 8
    assert all(c in "0123456789abcdef" for c in hash_part)


def test_mint_id_without_content_is_random():
    id1 = mint_id("design", "auth-flow")
    id2 = mint_id("design", "auth-flow")
    # Very likely different (probability of collision is 2^-32)
    assert id1.startswith("design.auth-flow~")
    assert id2.startswith("design.auth-flow~")
    # Both are 8 hex chars
    assert len(id1.split("~")[1]) == 8
    assert len(id2.split("~")[1]) == 8


def test_mint_id_anchor_form():
    # Anchors have no dot-kind prefix
    anchor_id = mint_id("", "auth-check")
    assert anchor_id.startswith("auth-check~")
    assert "." not in anchor_id.split("~")[0]


def test_mint_id_different_content_gives_different_hash():
    id1 = mint_id("design", "auth", "content A")
    id2 = mint_id("design", "auth", "content B")
    assert id1 != id2


# ---------------------------------------------------------------------------
# validate_marker tests
# ---------------------------------------------------------------------------

def test_validate_entry_valid():
    entry = EntryMarker(
        id="design.auth-flow~a1b2c3d4",
        kind="design",
        summary="JWT auth middleware",
        status="active",
        weight=0.85,
        tags=["scope:auth"],
        rationale="Missing causes bypass",
        applies="auth work",
        seeded_questions=["How does refresh work?"],
        depends_on=[],
        implements=None,
        supersedes=None,
        file="test.md",
        span=(1, 10),
    )
    vr = validate_marker(entry)
    assert vr.valid is True
    assert vr.errors == []


def test_validate_entry_bad_id():
    entry = EntryMarker(
        id="not-a-valid-id",
        kind="design",
        summary="Something",
        status="active",
        weight=None,
        tags=[],
        rationale=None,
        applies=None,
        seeded_questions=[],
        depends_on=[],
        implements=None,
        supersedes=None,
        file="test.md",
        span=(1, 5),
    )
    vr = validate_marker(entry)
    assert vr.valid is False
    assert any("id" in e for e in vr.errors)


def test_validate_entry_empty_summary():
    entry = EntryMarker(
        id="design.foo~a1b2c3d4",
        kind="design",
        summary="",
        status="active",
        weight=None,
        tags=[],
        rationale=None,
        applies=None,
        seeded_questions=[],
        depends_on=[],
        implements=None,
        supersedes=None,
        file="test.md",
        span=(1, 5),
    )
    vr = validate_marker(entry)
    assert vr.valid is False
    assert any("summary" in e for e in vr.errors)


def test_validate_entry_non_baseline_kind_warns():
    entry = EntryMarker(
        id="design.foo~a1b2c3d4",
        kind="customkind",
        summary="Something",
        status="active",
        weight=None,
        tags=[],
        rationale=None,
        applies=None,
        seeded_questions=[],
        depends_on=[],
        implements=None,
        supersedes=None,
        file="test.md",
        span=(1, 5),
    )
    vr = validate_marker(entry)
    # Should be valid (kind preserved) but have a warning
    assert vr.valid is True
    assert any("kind" in w for w in vr.warnings)


def test_validate_entry_non_baseline_status_warns():
    entry = EntryMarker(
        id="design.foo~a1b2c3d4",
        kind="design",
        summary="Something",
        status="complete",  # not in BASELINE_STATUSES
        weight=None,
        tags=[],
        rationale=None,
        applies=None,
        seeded_questions=[],
        depends_on=[],
        implements=None,
        supersedes=None,
        file="test.md",
        span=(1, 5),
    )
    vr = validate_marker(entry)
    assert vr.valid is True
    assert any("status" in w for w in vr.warnings)


def test_validate_anchor_valid():
    anchor = AnchorMarker(
        name="auth-check~f1e2d3c4",
        description="JWT validation point",
        seeded_questions=["What if expired?"],
        file="test.py",
        span=(5, 8),
    )
    vr = validate_marker(anchor)
    assert vr.valid is True
    assert vr.errors == []


def test_validate_anchor_bad_name():
    anchor = AnchorMarker(
        name="NoHash",
        description="Missing hash",
        seeded_questions=[],
        file="test.py",
        span=(1, 3),
    )
    vr = validate_marker(anchor)
    assert vr.valid is False
    assert any("name" in e for e in vr.errors)


def test_validate_anchor_empty_description():
    anchor = AnchorMarker(
        name="auth-check~f1e2d3c4",
        description="",
        seeded_questions=[],
        file="test.py",
        span=(1, 3),
    )
    vr = validate_marker(anchor)
    assert vr.valid is False
    assert any("description" in e for e in vr.errors)


def test_validate_binding_valid():
    binding = BindingMarker(
        local_id="impl-auth~a1b2c3d4",
        ref="spec.auth~xyz89012#FR3",
        comment=None,
        file="auth.py",
        offset=10,
        span=None,
    )
    vr = validate_marker(binding)
    assert vr.valid is True
    assert vr.errors == []


def test_validate_binding_bad_local_id():
    binding = BindingMarker(
        local_id="no-hash",
        ref="spec.auth~xyz89012#FR3",
        comment=None,
        file="auth.py",
        offset=10,
        span=None,
    )
    vr = validate_marker(binding)
    assert vr.valid is False
    assert any("local_id" in e for e in vr.errors)


def test_validate_binding_empty_ref():
    binding = BindingMarker(
        local_id="impl-auth~a1b2c3d4",
        ref="",
        comment=None,
        file="auth.py",
        offset=10,
        span=None,
    )
    vr = validate_marker(binding)
    assert vr.valid is False
    assert any("ref" in e for e in vr.errors)


# ---------------------------------------------------------------------------
# consts tests
# ---------------------------------------------------------------------------

def test_baseline_kinds_contains_all_v1_kinds():
    expected = {
        "design", "pattern", "spec", "lesson", "internal",
        "task", "milestone", "report", "audit", "research", "code"
    }
    assert set(BASELINE_KINDS) == expected


def test_baseline_statuses():
    assert "draft" in BASELINE_STATUSES
    assert "active" in BASELINE_STATUSES
    assert "deprecated" in BASELINE_STATUSES


def test_id_regex_matches_valid_ids():
    assert ID_REGEX.match("design.auth-flow~a1b2c3d4")
    assert ID_REGEX.match("spec.login~12345678")
    assert not ID_REGEX.match("design.auth~ABCDEFGH")  # uppercase in hash
    assert not ID_REGEX.match("design~a1b2c3d4")  # no dot


def test_anchor_id_regex_matches_valid():
    assert ANCHOR_ID_REGEX.match("auth-check~f1e2d3c4")
    assert not ANCHOR_ID_REGEX.match("auth.check~f1e2d3c4")  # has dot


def test_loose_anchor_regex():
    assert LOOSE_ANCHOR_REGEX.match("FR3")
    assert LOOSE_ANCHOR_REGEX.match("UT1")
    assert not LOOSE_ANCHOR_REGEX.match("fr3")  # lowercase
    assert not LOOSE_ANCHOR_REGEX.match("FR1-FR5")  # range, not loose


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_empty_content_returns_empty_result():
    result = parse_markers("")
    assert result.entries == []
    assert result.anchors == []
    assert result.bindings == []


def test_content_without_markers_returns_empty_result():
    content = "Just some regular text with no markers in it.\n"
    result = parse_markers(content)
    assert result.entries == []
    assert result.anchors == []
    assert result.bindings == []


def test_entry_span_is_1indexed():
    result = parse_markers(ENTRY_MARKDOWN)
    assert len(result.entries) == 1
    start, end = result.entries[0].span
    assert start >= 1
    assert end >= start


def test_anchor_span_is_1indexed():
    result = parse_markers(ANCHOR_MARKDOWN)
    assert len(result.anchors) == 1
    start, end = result.anchors[0].span
    assert start >= 1
    assert end >= start


def test_sql_style_entry_marker():
    content = """\
-- @scry.entry
-- id: design.db-schema~a1b2c3d4
-- kind: design
-- summary: Database schema design
-- status: active
-- weight: 0.7
-- tags: []
-- rationale: >
--   Schema decisions
-- applies: db work
-- seeded_questions: []
-- @scry.entry.end
"""
    result = parse_markers(content)
    assert len(result.entries) == 1
    assert result.entries[0].id == "design.db-schema~a1b2c3d4"


def test_lisp_double_semi_style_entry_marker():
    content = """\
;; @scry.entry
;; id: design.lisp-module~a1b2c3d4
;; kind: design
;; summary: Lisp module design
;; status: draft
;; weight: 0.5
;; tags: []
;; rationale: >
;;   Lisp test
;; applies: lisp work
;; seeded_questions: []
;; @scry.entry.end
"""
    result = parse_markers(content)
    assert len(result.entries) == 1
    assert result.entries[0].id == "design.lisp-module~a1b2c3d4"


def test_entry_with_depends_on():
    content = """\
<!-- @scry.entry
id: task.deploy~a1b2c3d4
kind: task
summary: Deploy to production
status: draft
weight: 0.8
tags: []
rationale: >
  Needed for release
applies: deploy
seeded_questions: []
depends_on:
  - task.build~12345678
  - task.test~87654321
@scry.entry.end -->
"""
    result = parse_markers(content)
    assert len(result.entries) == 1
    e = result.entries[0]
    assert "task.build~12345678" in e.depends_on
    assert "task.test~87654321" in e.depends_on


def test_bind_offset_is_1indexed():
    content = """\
line one
line two
# @scry.bind impl-x~a1b2c3d4 spec.x~12345678
line four
"""
    result = parse_markers(content)
    assert len(result.bindings) == 1
    assert result.bindings[0].offset == 3  # 1-indexed, 3rd line


def test_parse_result_file_field():
    result = parse_markers(ENTRY_MARKDOWN, file="path/to/file.md")
    assert result.entries[0].file == "path/to/file.md"


def test_parse_result_anchor_file_field():
    result = parse_markers(ANCHOR_MARKDOWN, file="src/auth.py")
    assert result.anchors[0].file == "src/auth.py"


# ---------------------------------------------------------------------------
# Block-comment styles (v1.0.1 — FR1 universality)
# ---------------------------------------------------------------------------

def test_jsdoc_entry():
    """JSDoc /** ... */ with ' * ' continuation prefix."""
    content = """\
/**
 * @scry.entry
 * id: design.foo~12345678
 * kind: design
 * summary: JSDoc block comment entry
 * status: active
 * weight: 0.5
 * tags: []
 * rationale: >
 *   Test rationale
 * applies: testing
 * seeded_questions: []
 * @scry.entry.end
 */
"""
    result = parse_markers(content)
    assert len(result.entries) == 1
    e = result.entries[0]
    assert e.id == "design.foo~12345678"
    assert e.kind == "design"
    assert "JSDoc" in e.summary
    assert e.status == "active"


def test_c_block_entry():
    """C-style /* ... */ with indented body (no per-line prefix)."""
    content = """\
/*
   @scry.entry
   id: design.foo~12345678
   kind: design
   summary: C-block comment entry
   status: active
   weight: 0.5
   tags: []
   rationale: >
     Test rationale
   applies: testing
   seeded_questions: []
   @scry.entry.end
*/
"""
    result = parse_markers(content)
    assert len(result.entries) == 1
    e = result.entries[0]
    assert e.id == "design.foo~12345678"
    assert "C-block" in e.summary


def test_c_block_inline_sentinels():
    """C-style /* @scry.entry ... @scry.entry.end */ on same-line sentinels."""
    content = """\
/* @scry.entry
   id: design.bar~87654321
   kind: design
   summary: Inline C-block sentinels
   status: draft
   weight: 0.4
   tags: []
   rationale: >
     Test
   applies: testing
   seeded_questions: []
   @scry.entry.end */
"""
    result = parse_markers(content)
    assert len(result.entries) == 1
    assert result.entries[0].id == "design.bar~87654321"


def test_jsdoc_anchor():
    """JSDoc-style @scry.anchor block."""
    content = """\
/**
 * @scry.anchor auth-point~f1e2d3c4
 * description: JSDoc anchor for auth entry point
 * seeded_questions:
 *   - How is JSDoc auth done?
 * @scry.anchor.end
 */
"""
    result = parse_markers(content)
    assert len(result.anchors) == 1
    a = result.anchors[0]
    assert a.name == "auth-point~f1e2d3c4"
    assert "JSDoc anchor" in a.description
    assert any("JSDoc" in q for q in a.seeded_questions)


def test_ocaml_block_entry():
    """OCaml (* ... *) with indented body."""
    content = """\
(*
   @scry.entry
   id: design.foo~12345678
   kind: design
   summary: OCaml block comment entry
   status: active
   weight: 0.5
   tags: []
   rationale: >
     Test rationale
   applies: testing
   seeded_questions: []
   @scry.entry.end
*)
"""
    result = parse_markers(content)
    assert len(result.entries) == 1
    assert result.entries[0].id == "design.foo~12345678"
    assert "OCaml" in result.entries[0].summary


def test_haskell_block_entry():
    """Haskell {- ... -} with indented body."""
    content = """\
{-
   @scry.entry
   id: design.foo~12345678
   kind: design
   summary: Haskell block comment entry
   status: active
   weight: 0.5
   tags: []
   rationale: >
     Test rationale
   applies: testing
   seeded_questions: []
   @scry.entry.end
-}
"""
    result = parse_markers(content)
    assert len(result.entries) == 1
    assert result.entries[0].id == "design.foo~12345678"
    assert "Haskell" in result.entries[0].summary


def test_powershell_block_entry():
    """PowerShell <# ... #> with indented body."""
    content = """\
<#
   @scry.entry
   id: design.foo~12345678
   kind: design
   summary: PowerShell block comment entry
   status: active
   weight: 0.5
   tags: []
   rationale: >
     Test rationale
   applies: testing
   seeded_questions: []
   @scry.entry.end
#>
"""
    result = parse_markers(content)
    assert len(result.entries) == 1
    assert result.entries[0].id == "design.foo~12345678"
    assert "PowerShell" in result.entries[0].summary


def test_jsdoc_bind_marker():
    """JSDoc-style @scry.bind single-line inside a regular comment."""
    content = """\
/**
 * @scry.bind my-impl~a1b2c3d4 design.foo~12345678
 */
"""
    result = parse_markers(content)
    assert len(result.bindings) == 1
    b = result.bindings[0]
    assert b.local_id == "my-impl~a1b2c3d4"
    assert b.ref == "design.foo~12345678"


def test_block_comment_existing_line_styles_still_pass():
    """Regression: existing line-comment styles unaffected by inference change."""
    python = """\
# @scry.entry
# id: design.py~a1b2c3d4
# kind: design
# summary: Python line-comment style
# status: active
# weight: 0.5
# tags: []
# rationale: >
#   Test
# applies: testing
# seeded_questions: []
# @scry.entry.end
"""
    ts = """\
// @scry.entry
// id: design.ts~b2c3d4e5
// kind: design
// summary: TypeScript line-comment style
// status: active
// weight: 0.5
// tags: []
// rationale: >
//   Test
// applies: testing
// seeded_questions: []
// @scry.entry.end
"""
    sql = """\
-- @scry.entry
-- id: design.sql~c3d4e5f6
-- kind: design
-- summary: SQL line-comment style
-- status: active
-- weight: 0.5
-- tags: []
-- rationale: >
--   Test
-- applies: testing
-- seeded_questions: []
-- @scry.entry.end
"""
    lisp = """\
;; @scry.entry
;; id: design.lisp~d4e5f6a7
;; kind: design
;; summary: Lisp double-semi style
;; status: active
;; weight: 0.5
;; tags: []
;; rationale: >
;;   Test
;; applies: testing
;; seeded_questions: []
;; @scry.entry.end
"""
    for content, expected_id in [
        (python, "design.py~a1b2c3d4"),
        (ts, "design.ts~b2c3d4e5"),
        (sql, "design.sql~c3d4e5f6"),
        (lisp, "design.lisp~d4e5f6a7"),
    ]:
        result = parse_markers(content)
        assert len(result.entries) == 1, f"Expected 1 entry for {expected_id}"
        assert result.entries[0].id == expected_id


# ---------------------------------------------------------------------------
# Block-comment styles (v1.0.1 fix — FR1 universality)
# ---------------------------------------------------------------------------

def test_jsdoc_entry_marker():
    """JSDoc /** ... */ with * continuation lines."""
    content = """\
/**
 * @scry.entry
 * id: design.foo~12345678
 * kind: design
 * summary: JSDoc block entry
 * status: active
 * weight: 0.5
 * tags: []
 * rationale: >
 *   JSDoc rationale
 * applies: testing
 * seeded_questions: []
 * @scry.entry.end
 */
"""
    result = parse_markers(content)
    assert len(result.entries) == 1
    e = result.entries[0]
    assert e.id == "design.foo~12345678"
    assert e.kind == "design"
    assert "JSDoc block entry" in e.summary
    assert e.status == "active"


def test_c_block_entry_marker():
    """C-style /* ... */ with indented body."""
    content = """\
/*
   @scry.entry
   id: design.foo~12345678
   kind: design
   summary: C block entry
   status: active
   weight: 0.5
   tags: []
   rationale: >
     C block rationale
   applies: testing
   seeded_questions: []
   @scry.entry.end
*/
"""
    result = parse_markers(content)
    assert len(result.entries) == 1
    e = result.entries[0]
    assert e.id == "design.foo~12345678"
    assert "C block entry" in e.summary


def test_c_block_anchor_marker():
    """C-style /* ... */ anchor."""
    content = """\
/*
   @scry.anchor auth-check~f1e2d3c4
   description: C-block anchor description
   seeded_questions:
     - What happens here?
   @scry.anchor.end
*/
"""
    result = parse_markers(content)
    assert len(result.anchors) == 1
    a = result.anchors[0]
    assert a.name == "auth-check~f1e2d3c4"
    assert "C-block anchor description" in a.description


def test_ocaml_block_entry_marker():
    """OCaml (* ... *) block comment."""
    content = """\
(*
   @scry.entry
   id: design.foo~12345678
   kind: design
   summary: OCaml block entry
   status: draft
   weight: 0.5
   tags: []
   rationale: >
     OCaml rationale
   applies: testing
   seeded_questions: []
   @scry.entry.end
*)
"""
    result = parse_markers(content)
    assert len(result.entries) == 1
    assert result.entries[0].id == "design.foo~12345678"
    assert "OCaml block entry" in result.entries[0].summary


def test_haskell_block_entry_marker():
    """Haskell {- ... -} block comment."""
    content = """\
{-
   @scry.entry
   id: design.foo~12345678
   kind: design
   summary: Haskell block entry
   status: draft
   weight: 0.5
   tags: []
   rationale: >
     Haskell rationale
   applies: testing
   seeded_questions: []
   @scry.entry.end
-}
"""
    result = parse_markers(content)
    assert len(result.entries) == 1
    assert result.entries[0].id == "design.foo~12345678"
    assert "Haskell block entry" in result.entries[0].summary


def test_powershell_block_entry_marker():
    """PowerShell <# ... #> block comment."""
    content = """\
<#
   @scry.entry
   id: design.foo~12345678
   kind: design
   summary: PowerShell block entry
   status: draft
   weight: 0.5
   tags: []
   rationale: >
     PowerShell rationale
   applies: testing
   seeded_questions: []
   @scry.entry.end
#>
"""
    result = parse_markers(content)
    assert len(result.entries) == 1
    assert result.entries[0].id == "design.foo~12345678"
    assert "PowerShell block entry" in result.entries[0].summary


def test_jsdoc_bind_marker():
    """JSDoc-style bind marker with * continuation."""
    content = """\
/**
 * @scry.bind impl-auth~a1b2c3d4 spec.auth~xyz89012#FR3
 * This implements JWT validation per FR3.
 * @scry.bind.end
 */
"""
    result = parse_markers(content)
    assert len(result.bindings) == 1
    b = result.bindings[0]
    assert b.local_id == "impl-auth~a1b2c3d4"
    assert b.ref == "spec.auth~xyz89012#FR3"
    assert b.comment is not None
    assert "JWT validation" in b.comment


def test_block_comment_existing_line_styles_still_work():
    """Regression: existing line-comment styles (Python, TS, SQL, Lisp) still parse."""
    styles = [
        ("# @scry.entry\n# id: design.foo~12345678\n# kind: design\n# summary: Python\n"
         "# status: active\n# weight: 0.5\n# tags: []\n# rationale: >\n#   r\n"
         "# applies: t\n# seeded_questions: []\n# @scry.entry.end\n"),
        ("// @scry.entry\n// id: design.foo~12345678\n// kind: design\n// summary: TS\n"
         "// status: active\n// weight: 0.5\n// tags: []\n// rationale: >\n//   r\n"
         "// applies: t\n// seeded_questions: []\n// @scry.entry.end\n"),
        ("-- @scry.entry\n-- id: design.foo~12345678\n-- kind: design\n-- summary: SQL\n"
         "-- status: active\n-- weight: 0.5\n-- tags: []\n-- rationale: >\n--   r\n"
         "-- applies: t\n-- seeded_questions: []\n-- @scry.entry.end\n"),
        (";; @scry.entry\n;; id: design.foo~12345678\n;; kind: design\n;; summary: Lisp\n"
         ";; status: active\n;; weight: 0.5\n;; tags: []\n;; rationale: >\n;;   r\n"
         ";; applies: t\n;; seeded_questions: []\n;; @scry.entry.end\n"),
    ]
    for content in styles:
        result = parse_markers(content)
        assert len(result.entries) == 1, f"Failed for:\n{content}"
        assert result.entries[0].id == "design.foo~12345678"


# ---------------------------------------------------------------------------
# FR12: cycle detection (check_cycles)
# ---------------------------------------------------------------------------

from scry_parse import check_cycles


def _make_entry(id_: str, depends_on: list[str] | None = None) -> EntryMarker:
    """Construct a minimal EntryMarker for cycle-detection tests."""
    return EntryMarker(
        id=id_,
        kind="design",
        summary="test",
        status="active",
        weight=0.5,
        tags=[],
        rationale=None,
        applies=None,
        seeded_questions=[],
        depends_on=depends_on or [],
        implements=None,
        supersedes=None,
        file="",
        span=(0, 0),
    )


def test_check_cycles_empty():
    """Empty marker list returns no cycles."""
    assert check_cycles([]) == []


def test_check_cycles_no_deps():
    """Markers without depends_on have no cycles."""
    markers = [
        _make_entry("design.a~00000001"),
        _make_entry("design.b~00000002"),
    ]
    assert check_cycles(markers) == []


def test_check_cycles_linear_chain():
    """A → B → C with no back-edge is acyclic."""
    markers = [
        _make_entry("design.a~00000001", ["design.b~00000002"]),
        _make_entry("design.b~00000002", ["design.c~00000003"]),
        _make_entry("design.c~00000003"),
    ]
    assert check_cycles(markers) == []


def test_check_cycles_self_loop():
    """A depends_on A is a cycle."""
    markers = [_make_entry("design.a~00000001", ["design.a~00000001"])]
    errors = check_cycles(markers)
    assert len(errors) == 1
    assert "cycle detected" in errors[0]
    assert "design.a~00000001" in errors[0]


def test_check_cycles_two_node_cycle():
    """A → B → A is a cycle."""
    markers = [
        _make_entry("design.a~00000001", ["design.b~00000002"]),
        _make_entry("design.b~00000002", ["design.a~00000001"]),
    ]
    errors = check_cycles(markers)
    assert len(errors) >= 1
    assert any("cycle detected" in e for e in errors)


def test_check_cycles_three_node_cycle():
    """A → B → C → A is a cycle."""
    markers = [
        _make_entry("design.a~00000001", ["design.b~00000002"]),
        _make_entry("design.b~00000002", ["design.c~00000003"]),
        _make_entry("design.c~00000003", ["design.a~00000001"]),
    ]
    errors = check_cycles(markers)
    assert len(errors) >= 1
    assert any("cycle detected" in e for e in errors)
    # The cycle path should contain all three nodes
    full_error = " ".join(errors)
    assert "design.a~00000001" in full_error
    assert "design.b~00000002" in full_error
    assert "design.c~00000003" in full_error


def test_check_cycles_unresolved_dep_not_a_cycle():
    """A depends on B but B is not in markers — not a cycle, just unresolved."""
    markers = [_make_entry("design.a~00000001", ["design.b~00000002"])]
    assert check_cycles(markers) == []


def test_check_cycles_ignores_non_entry_markers():
    """AnchorMarker and BindingMarker objects are silently skipped."""
    from scry_parse.markers import AnchorMarker, BindingMarker
    anchor = AnchorMarker(name="a~00000001", description="d", seeded_questions=[], file="", span=(0, 0))
    binding = BindingMarker(local_id="a~00000001", ref="design.b~00000002", comment=None, file="", offset=0, span=None)
    # No crash, no false cycles
    assert check_cycles([anchor, binding]) == []


# ---------------------------------------------------------------------------
# FR13: Binding Semantics — no restrictions on source→target combinations
# ---------------------------------------------------------------------------

def test_fr13_any_source_to_any_target_valid():
    """FR13: any source can bind to any target — validator must not restrict.

    Per spec: 'Implementations MUST NOT restrict valid binding combinations.'
    """
    from scry_parse.markers import BindingMarker

    # Cross-kind combinations that might otherwise be restricted
    combinations = [
        ("fix~00000001", "spec.auth~a1b2c3d4"),
        ("fix~00000001", "design.auth~a1b2c3d4"),
        ("fix~00000001", "pattern.foo~a1b2c3d4"),
        ("fix~00000001", "lesson.foo~a1b2c3d4"),
        ("fix~00000001", "audit.foo~a1b2c3d4"),
        ("fix~00000001", "milestone.foo~a1b2c3d4"),
        ("fix~00000001", "code.foo~a1b2c3d4"),
        ("fix~00000001", "task.foo~a1b2c3d4"),
        # anchor-qualified refs (strict mode)
        ("fix~00000001", "spec.auth~a1b2c3d4#FR1"),
        ("fix~00000001", "spec.auth~a1b2c3d4#UT1"),
        ("fix~00000001", "design.x~a1b2c3d4#DR7"),
    ]
    for local_id, ref in combinations:
        marker = BindingMarker(
            local_id=local_id,
            ref=ref,
            comment=None,
            file="test.py",
            offset=0,
            span=None,
        )
        result = validate_marker(marker)
        assert result.valid, (
            f"FR13 violation: validate_marker rejected binding "
            f"{local_id!r} → {ref!r} with errors: {result.errors}"
        )


def test_fr13_bind_with_comment_any_kind():
    """FR13: comment field does not affect binding validity."""
    from scry_parse.markers import BindingMarker

    marker = BindingMarker(
        local_id="thing~00000001",
        ref="audit.security~deadbeef#AF7",
        comment="addresses audit finding; see also lesson.csrf-bypass~cafebabe",
        file="src/app.py",
        offset=10,
        span=None,
    )
    result = validate_marker(marker)
    assert result.valid, f"FR13: comment-bearing binding rejected: {result.errors}"


def test_fr13_bind_parsed_cross_kind():
    """FR13: parsed cross-kind bindings from source text are accepted."""
    content = """\
# @scry.bind fix~00000001 spec.auth~a1b2c3d4#FR1
# @scry.bind fix~00000001 design.system~b2c3d4e5
# @scry.bind impl~00000002 lesson.perf~c3d4e5f6 rationale source
def do_thing(): pass
"""
    result = parse_markers(content, language="python", file="src/thing.py")
    bindings = [m for m in result.markers if isinstance(m, BindingMarker)]
    assert len(bindings) == 3, f"Expected 3 bindings, got {len(bindings)}"
    for b in bindings:
        vr = validate_marker(b)
        assert vr.valid, f"FR13: cross-kind binding invalid: {vr.errors}"


# ---------------------------------------------------------------------------
# FR14: Soft References — ID-shaped strings outside @scry.bind are NOT extracted
# ---------------------------------------------------------------------------

def test_fr14_id_in_prose_not_extracted():
    """FR14: ID-shaped strings in prose text are not parsed as BindingMarkers."""
    content = """\
This file is related to design.auth-flow~a1b2c3d4 and also
references pattern.caching~b2c3d4e5. See spec.x~cafebabe for more.
No markers here — just narrative text mentioning IDs.
"""
    result = parse_markers(content, language="markdown", file="README.md")
    bindings = [m for m in result.markers if isinstance(m, BindingMarker)]
    assert bindings == [], (
        f"FR14 violation: {len(bindings)} binding(s) extracted from prose: "
        + str([(b.local_id, b.ref) for b in bindings])
    )


def test_fr14_id_in_yaml_body_not_extracted():
    """FR14: ID-shaped strings inside @scry.entry YAML fields are not extracted as bindings."""
    content = """\
<!-- @scry.entry
id: design.foo~a1b2c3d4
kind: design
status: active
summary: "depends on spec.auth~b2c3d4e5; see also pattern.x~c3d4e5f6 for details"
rationale: "without pattern.x~c3d4e5f6 this fails"
applies: "modifying design.foo~a1b2c3d4"
seeded_questions: []
tags: []
weight: 0.5
@scry.entry.end -->
"""
    result = parse_markers(content, language=None, file="doc.md")
    bindings = [m for m in result.markers if isinstance(m, BindingMarker)]
    assert bindings == [], (
        f"FR14 violation: ID-shaped strings in YAML body extracted as bindings: "
        + str([(b.local_id, b.ref) for b in bindings])
    )


def test_fr14_id_in_code_comment_not_extracted():
    """FR14: ID-shaped strings in non-scry code comments are not extracted."""
    content = """\
# This implementation relates to design.auth~a1b2c3d4 (soft reference, not formal)
# See also: lesson.security~cafebabe for background
def authenticate(user):
    pass  # implements spec.auth~b2c3d4e5 roughly
"""
    result = parse_markers(content, language="python", file="auth.py")
    bindings = [m for m in result.markers if isinstance(m, BindingMarker)]
    assert bindings == [], (
        f"FR14 violation: soft refs in code comments extracted as bindings: "
        + str([(b.local_id, b.ref) for b in bindings])
    )


def test_fr14_id_in_bind_comment_not_extracted_as_extra_binding():
    """FR14: ID-shaped strings in @scry.bind comment slots are soft refs — not extra bindings."""
    content = """\
# @scry.bind fix~00000001 audit.sec~a1b2c3d4 also fixes lesson.old-bug~b2c3d4e5
def patch(): pass
"""
    result = parse_markers(content, language="python", file="patch.py")
    bindings = [m for m in result.markers if isinstance(m, BindingMarker)]
    # Only ONE binding — the formal one. The lesson.old-bug~b2c3d4e5 in the
    # comment slot is a soft reference; it is NOT extracted as a separate BindingMarker.
    assert len(bindings) == 1, (
        f"FR14 violation: comment-slot soft ref extracted as extra binding "
        f"(got {len(bindings)} bindings)"
    )
    assert bindings[0].ref == "audit.sec~a1b2c3d4"


def test_fr14_soft_refs_in_multiple_contexts():
    """FR14: soft refs across various non-formal positions are never extracted."""
    content = """\
---
title: System Overview
relates_to: design.system~a1b2c3d4
---

# Overview

This document is informed by spec.auth~b2c3d4e5 and design.cache~c3d4e5f6.
The implementation at code.server~d4e5f6a7 is the canonical reference.

See milestone.v1~e5f6a7b8 for completion criteria.
"""
    result = parse_markers(content, language="markdown", file="overview.md")
    bindings = [m for m in result.markers if isinstance(m, BindingMarker)]
    assert bindings == [], (
        f"FR14 violation: {len(bindings)} binding(s) from non-formal positions"
    )
