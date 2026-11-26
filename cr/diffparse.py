"""Parse a unified diff into added lines with their line numbers in the new file."""
import re
from dataclasses import dataclass, field

HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


@dataclass
class FileDiff:
    path: str
    added: list[tuple[int, str]] = field(default_factory=list)  # (new line number, text)


def parse(diff: str) -> list[FileDiff]:
    files: list[FileDiff] = []
    cur: FileDiff | None = None
    new_no = 0
    for raw in diff.splitlines():
        if raw.startswith("+++ "):
            p = raw[4:].strip()
            cur = FileDiff(path=p[2:] if p.startswith("b/") else p)
            if p != "/dev/null":
                files.append(cur)
            continue
        if raw.startswith("--- ") or raw.startswith("diff --git") or raw.startswith("index "):
            continue
        m = HUNK.match(raw)
        if m:
            new_no = int(m.group(1))
            continue
        if cur is None:
            continue
        if raw.startswith("+"):
            cur.added.append((new_no, raw[1:]))
            new_no += 1
        elif raw.startswith("-"):
            continue
        elif raw.startswith("\\"):
            continue
        else:
            new_no += 1
    return files
