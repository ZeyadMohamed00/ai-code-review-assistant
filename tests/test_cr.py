import httpx
import pytest
from fastapi.testclient import TestClient

from cr import github
from cr.diffparse import parse
from cr.main import app
from cr.rules import review_diff
from eval.run_eval import evaluate

c = TestClient(app)
H = {"X-Client-Id": "crclient-000001"}

DIFF = """diff --git a/m.py b/m.py
--- a/m.py
+++ b/m.py
@@ -10,3 +10,5 @@ def x():
     a = 1
-    b = 2
+    b = eval(s)
+    c = 3
     d = 4
"""


def test_diff_parser_line_numbers():
    f = parse(DIFF)[0]
    assert f.path == "m.py" and f.added == [(11, "    b = eval(s)"), (12, "    c = 3")]


def test_rules_report_correct_line_and_ignore_comments_and_other_files():
    out = review_diff(DIFF)
    assert [(x.line, x.category) for x in out] == [(11, "eval-exec")]
    assert review_diff(DIFF.replace("m.py", "m.js")) == []
    assert review_diff(DIFF.replace("b = eval(s)", "# eval(s) is bad")) == []


def test_benchmark_numbers_are_stable_and_honest():
    r = evaluate()
    assert r["by_kind"]["pattern"]["rate"] == 1.0
    assert (
        r["by_kind"]["logic"]["found"] == 0
    )  # rules do not catch logic bugs, and the benchmark says so
    assert 0 < r["detection_rate"] < 1 and r["false_positives"] == 3


def test_api_review_and_history_isolated():
    r = c.post("/review/diff", headers=H, json={"diff": DIFF}).json()
    assert r["reviewer"] == "rules" and r["findings"][0]["category"] == "eval-exec"
    assert len(c.get("/reviews", headers=H).json()) == 1
    assert c.get("/reviews", headers={"X-Client-Id": "other-client-001"}).json() == []
    assert c.post("/review/diff", json={"diff": DIFF}).status_code == 400
    assert c.post("/review/diff", headers=H, json={"diff": ""}).status_code == 422


def test_pr_url_validation_and_fetch_with_mock_transport():
    assert github.parse_pr_url("https://github.com/a/b/pull/12") == ("a", "b", 12)
    with pytest.raises(ValueError):
        github.parse_pr_url("https://evil.example/a/b/pull/1")
    ok = httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(200, text=DIFF)))
    assert github.fetch_diff("a", "b", 1, ok) == DIFF
    nf = httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(404)))
    with pytest.raises(LookupError):
        github.fetch_diff("a", "b", 1, nf)
    assert c.post("/review/pr", headers=H, json={"url": "https://example.com/x"}).status_code == 422


def test_post_review_builds_comments_and_needs_token(monkeypatch):
    from cr.rules import Finding

    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    with pytest.raises(PermissionError):
        github.post_review("a", "b", 1, "sha", [])
    monkeypatch.setenv("GITHUB_TOKEN", "x")
    seen = {}

    def handler(req):
        import json

        seen.update(json.loads(req.content))
        return httpx.Response(200, json={"id": 1})

    cl = httpx.Client(transport=httpx.MockTransport(handler))
    github.post_review("a", "b", 1, "sha", [Finding("m.py", 11, "eval-exec", "high", "msg")], cl)
    assert seen["comments"][0] == {
        "path": "m.py",
        "line": 11,
        "side": "RIGHT",
        "body": "**eval-exec** (high): msg",
    }


def test_samples_endpoint():
    s = c.get("/samples").json()
    assert len(s) == 40 and s[0]["diff"].startswith("--- a/app.py")
