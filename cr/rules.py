"""Rule-based reviewer. Looks only at ADDED lines of .py files. Each rule is a regex plus an optional check.
These are deliberately simple pattern rules: they catch well-known bug patterns, NOT logic errors."""
import re
from dataclasses import dataclass, asdict
from .diffparse import parse


@dataclass
class Finding:
    file: str
    line: int
    category: str
    severity: str
    message: str
    source: str = "rules"

    def dict(self):
        return asdict(self)


def _strip_comment(s: str) -> str:
    return re.sub(r"\s+#.*$", "", s)


SQL_EXEC = re.compile(r"\.execute\(\s*(f[\"']|[\"'][^\"']*[\"']\s*(%|\+)|[^\"')]*\+|[\"'][^\"']*[\"']\.format)")
RULES = [
    ("mutable-default", "medium", re.compile(r"def\s+\w+\(.*=\s*(\[\]|\{\}|set\(\))\s*[,)]"), "Mutable default argument is shared between calls."),
    ("bare-except", "medium", re.compile(r"^\s*except\s*:"), "Bare except hides real errors (also catches KeyboardInterrupt)."),
    ("none-compare", "low", re.compile(r"[=!]=\s*None\b"), "Compare to None with 'is' / 'is not'."),
    ("sql-injection", "high", SQL_EXEC, "SQL built by string formatting. Use parameterized queries."),
    ("hardcoded-secret", "high", re.compile(r"(?i)\b(password|passwd|secret|api_?key|token)\w*\s*=\s*[\"'][^\"']{8,}[\"']"), "Hardcoded secret. Load it from the environment."),
    ("eval-exec", "high", re.compile(r"(?<![\w.])(eval|exec)\("), "eval/exec on dynamic input can run arbitrary code."),
    ("shell-true", "high", re.compile(r"subprocess\.\w+\(.*shell\s*=\s*True"), "shell=True with dynamic input allows command injection."),
    ("yaml-unsafe-load", "high", re.compile(r"yaml\.load\((?!.*Loader)"), "yaml.load without a safe Loader can construct arbitrary objects."),
    ("is-literal", "medium", re.compile(r"\bis(\s+not)?\s+([\"'\d])"), "'is' compares identity, not value, for literals."),
    ("debug-enabled", "medium", re.compile(r"\b(debug\s*=\s*True)"), "Debug mode must not be enabled in production."),
    ("unclosed-file", "medium", re.compile(r"=\s*open\("), "File opened without a context manager may never be closed."),
]


def review_diff(diff: str) -> list[Finding]:
    out: list[Finding] = []
    for fd in parse(diff):
        if not fd.path.endswith(".py"):
            continue
        lines = fd.added
        for i, (no, text) in enumerate(lines):
            code = _strip_comment(text)
            if code.lstrip().startswith("#"):
                continue
            for cat, sev, rx, msg in RULES:
                if rx.search(code):
                    out.append(Finding(fd.path, no, cat, sev, msg))
            # swallowed exception: except ...: followed directly by pass
            if re.match(r"^\s*except\b.*:\s*$", code) and i + 1 < len(lines) and lines[i + 1][1].strip() == "pass":
                out.append(Finding(fd.path, lines[i + 1][0], "swallowed-exception", "medium", "Exception is silently ignored."))
            # requests without timeout: look at this line and the next 3 added lines
            if re.search(r"\brequests\.(get|post|put|delete|patch)\(", code):
                window = " ".join(t for _, t in lines[i:i + 4])
                if "timeout" not in window:
                    out.append(Finding(fd.path, no, "no-timeout", "medium", "HTTP call without a timeout can hang forever."))
    seen, uniq = set(), []
    for f in out:
        k = (f.file, f.line, f.category)
        if k not in seen:
            seen.add(k); uniq.append(f)
    return uniq
