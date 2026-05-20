# scry-parse

Python parser for the [scry-spec](https://github.com/prmichaelsen/scry-spec) marker format. Conformant with scry-spec v1.1.1 (framing patch over v1.1.0 FR4.B Extras Field — no normative changes).

## Install

```bash
uv pip install scry-parse
# or:
pip install scry-parse
```

## Usage

```python
from scry_parse import (
    parse_markers,
    validate_marker,
    check_cycles,
    mint_id,
    BASELINE_KINDS,
    BASELINE_STATUSES,
    EXTRAS_SIZE_CAP_BYTES,  # FR4.B (v1.1.0)
)

# Parse markers from file content
with open("my_file.md") as f:
    content = f.read()

result = parse_markers(content)

# Access by type
for entry in result.entries:
    print(entry.id, entry.kind, entry.summary)

for anchor in result.anchors:
    print(anchor.name, anchor.description)

for binding in result.bindings:
    print(binding.local_id, binding.ref)

# Or iterate all markers together
for marker in result.markers:
    print(type(marker).__name__, marker)

# Validate a parsed marker
vr = validate_marker(result.entries[0])
if not vr.valid:
    print(vr.errors)
if vr.warnings:
    print(vr.warnings)

# Detect cycles in depends_on relationships (FR12)
cycle_errors = check_cycles(result.entries)
if cycle_errors:
    for err in cycle_errors:
        print(err)  # "cycle detected: design.a~... → design.b~... → design.a~..."

# Generate a new marker ID
entry_id = mint_id("design", "auth-flow")           # random hash
entry_id = mint_id("design", "auth-flow", content)  # deterministic hash from content
```

## Supported comment styles

Comment-prefix detection is automatic via YAML-key inference — no language hint required.

### Line comments

| Style | Example |
|---|---|
| HTML/Markdown | `<!-- @scry.entry ... @scry.entry.end -->` |
| Python/Shell | `# @scry.entry ... # @scry.entry.end` |
| TypeScript/JS | `// @scry.entry ... // @scry.entry.end` |
| SQL | `-- @scry.entry ... -- @scry.entry.end` |
| Lisp | `;; @scry.entry ... ;; @scry.entry.end` |

### Block comments (v1.0.1+)

| Style | Example |
|---|---|
| JSDoc / Java | `/** @scry.entry ... * @scry.entry.end */` with `*` continuation |
| C / C++ | `/* @scry.entry ... @scry.entry.end */` |
| OCaml | `(* @scry.entry ... @scry.entry.end *)` |
| Haskell | `{- @scry.entry ... @scry.entry.end -}` |
| PowerShell | `<# @scry.entry ... @scry.entry.end #>` |

Example JSDoc marker:

```ts
/**
 * @scry.entry
 * id: design.auth-flow~a1b2c3d4
 * kind: design
 * summary: JWT auth middleware
 * status: active
 * @scry.entry.end
 */
```

## Public API

| Symbol | Description |
|---|---|
| `parse_markers(content, language=None, file="")` | Parse all scry markers from text. Returns `ParseResult`. |
| `validate_marker(marker)` | Validate a marker against spec rules. Returns `ValidationResult`. |
| `check_cycles(markers)` | Detect cycles in `depends_on` graph. Returns `list[str]` of error messages. |
| `mint_id(kind, name, content=None)` | Generate a spec-conformant marker ID. |
| `BASELINE_KINDS` | Tuple of standard kind values from scry-spec v1.0. |
| `BASELINE_STATUSES` | Tuple of standard status values (`draft`, `active`, `deprecated`). |
| `EXTRAS_SIZE_CAP_BYTES` | FR4.B v1.1.0 size cap (4096) for serialized `extras` payload. |

### Dataclasses

- **`ParseResult`** — `entries: list[EntryMarker]`, `anchors: list[AnchorMarker]`, `bindings: list[BindingMarker]`, `markers` property (all three combined)
- **`EntryMarker`** — `id`, `kind`, `summary`, `status`, `weight`, `tags`, `rationale`, `applies`, `seeded_questions`, `depends_on`, `implements`, `supersedes`, `file`, `span`, `extras` (FR4.B v1.1.0; `dict[str, Any] | None`, preserved structurally)
- **`AnchorMarker`** — `name`, `description`, `seeded_questions`, `file`, `span`
- **`BindingMarker`** — `local_id`, `ref`, `comment`, `file`, `offset`, `span`
- **`ValidationResult`** — `valid`, `errors`, `warnings` (FR4.B SHOULD-diagnostics for `extras`: empty map, nested/list value, oversize)

## License

MIT — see [LICENSE](LICENSE).
