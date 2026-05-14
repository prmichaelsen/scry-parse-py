"""ID generation for scry-spec v1.0 markers."""
from __future__ import annotations

import hashlib
import secrets


def mint_id(kind: str, name: str, content: str | None = None) -> str:
    """Generate a spec-conformant marker ID: '{kind}.{name}~{hash}'.

    For entry markers, the full ID is '{kind}.{name}~{8hexchars}'.
    For anchor/impl/test markers, the convention is '{name}~{8hexchars}'
    (no dot prefix) — callers should pass name only without kind in that case,
    or use kind="" and name="name~...".

    Args:
        kind: The marker kind (e.g. "design", "spec"). Use "" for anchors/impls/tests
              where the ID format is just '{name}~{hash}'.
        name: The human-readable name portion (e.g. "auth-flow").
        content: Optional content for deterministic hash. If None, a random
                 4-byte hex string is generated.

    Returns:
        A spec-conformant ID string.
    """
    if content is not None:
        hash_hex = hashlib.sha256(content.encode()).hexdigest()[:8]
    else:
        hash_hex = secrets.token_hex(4)  # 4 bytes = 8 hex chars

    if kind:
        return f"{kind}.{name}~{hash_hex}"
    else:
        return f"{name}~{hash_hex}"
