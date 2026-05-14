"""Constants for scry-spec v1.0: baseline kinds, statuses, and ID regexes."""
import re

BASELINE_KINDS = (
    "design", "pattern", "spec", "lesson", "internal",
    "task", "milestone",
    "report", "audit", "research",
    "code",
)

BASELINE_STATUSES = ("draft", "active", "deprecated")

# ID validation regexes per scry-spec v1.0
# Entry/doc IDs: kind.name~8hexchars
ID_REGEX = re.compile(r'^[a-z]+\.[a-z0-9-]+~[a-f0-9]{8}$')
# Anchor/impl/test IDs: name~8hexchars (no dot)
ANCHOR_ID_REGEX = re.compile(r'^[a-z0-9-]+~[a-f0-9]{8}$')
# Loose anchor IDs used in refs: uppercase letters followed by digits (e.g. FR3, UT1)
LOOSE_ANCHOR_REGEX = re.compile(r'^[A-Z]+[0-9]+$')
