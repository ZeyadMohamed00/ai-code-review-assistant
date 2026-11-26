"""GitHub API: fetch a PR diff, and (with a token) post review comments."""
import os
import re
import httpx

PR_URL = re.compile(r"^https://github\.com/([\w.-]+)/([\w.-]+)/pull/(\d+)/?$")


def parse_pr_url(url: str):
    m = PR_URL.match(url.strip())
    if not m:
        raise ValueError("Expected a URL like https://github.com/owner/repo/pull/123")
    return m.group(1), m.group(2), int(m.group(3))


def fetch_diff(owner: str, repo: str, number: int, client: httpx.Client | None = None) -> str:
    c = client or httpx.Client(timeout=20)
    headers = {"Accept": "application/vnd.github.v3.diff", "User-Agent": "code-review-assistant"}
    if os.getenv("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    r = c.get(f"https://api.github.com/repos/{owner}/{repo}/pulls/{number}", headers=headers)
    if r.status_code == 404:
        raise LookupError("PR not found (or private)")
    r.raise_for_status()
    if len(r.text) > 400_000:
        raise ValueError("Diff too large for this demo (400 KB limit)")
    return r.text


def post_review(owner, repo, number, commit_sha, findings, client: httpx.Client | None = None):
    """Needs GITHUB_TOKEN with pull-request write access. Not enabled in the public demo."""
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise PermissionError("GITHUB_TOKEN not configured")
    c = client or httpx.Client(timeout=20)
    body = {"commit_id": commit_sha, "event": "COMMENT", "body": f"Automated review: {len(findings)} possible issue(s).",
            "comments": [{"path": f.file, "line": f.line, "side": "RIGHT", "body": f"**{f.category}** ({f.severity}): {f.message}"} for f in findings]}
    r = c.post(f"https://api.github.com/repos/{owner}/{repo}/pulls/{number}/reviews", json=body,
               headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "User-Agent": "code-review-assistant"})
    r.raise_for_status()
    return r.json()
