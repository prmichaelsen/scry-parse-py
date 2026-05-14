# scry-parse

Python parser for the [scry-spec v1.0](https://github.com/prmichaelsen/scry-spec) marker format.

## Install

```bash
uv pip install scry-parse
# or:
pip install scry-parse
```

## Usage

```python
from scry_parse import parse_markers, validate_marker, mint_id, BASELINE_KINDS, BASELINE_STATUSES

# Parse markers from file content
with open("my_file.md") as f:
    content = f.read()

result = parse_markers(content)

for entry in result.entries:
    print(entry.id, entry.kind, entry.summary)

for anchor in result.anchors:
    print(anchor.name, anchor.description)

for binding in result.bindings:
    print(binding.local_id, binding.ref)

# Validate a parsed marker
vr = validate_marker(result.entries[0])
if not vr.valid:
    print(vr.errors)

# Generate a new marker ID
entry_id = mint_id("design", "auth-flow")          # random hash
entry_id = mint_id("design", "auth-flow", content)  # deterministic hash
```

## Supported comment styles

- HTML/Markdown: `<!-- @scry.entry ... @scry.entry.end -->`
- Python/Shell: `# @scry.entry ... # @scry.entry.end`
- TypeScript/JS: `// @scry.entry ... // @scry.entry.end`
- SQL: `-- @scry.entry ... -- @scry.entry.end`
- Lisp: `;; @scry.entry ... ;; @scry.entry.end`

## License

MIT — see [LICENSE](LICENSE).
