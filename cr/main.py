import sys, pathlib
from fastapi import FastAPI, Depends, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from . import db as D, github, llm
from .rules import review_diff

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from eval.dataset import CASES, diff_for  # noqa: E402
from eval.run_eval import evaluate  # noqa: E402


def owner(x_client_id: str = Header(default="")):
    if not (8 <= len(x_client_id) <= 64) or not x_client_id.replace("-", "").isalnum():
        raise HTTPException(400, "Missing or invalid X-Client-Id header")
    return x_client_id


class DiffIn(BaseModel):
    diff: str = Field(min_length=1, max_length=400_000)


class PrIn(BaseModel):
    url: str = Field(max_length=300)


def run_review(diff: str):
    findings = review_diff(diff)
    reviewer = "rules"
    if llm.enabled():  # pragma: no cover
        findings += llm.review_diff(diff); reviewer = "rules+llm"
    return reviewer, findings


def create_app():
    D.init()
    app = FastAPI(title="AI Code Review Assistant", version="1.0.0")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

    def save(o, source, reviewer, findings):
        with D.Session() as s:
            r = D.Review(owner=o, source=source[:300], reviewer=reviewer, findings=[f.dict() for f in findings]); s.add(r); s.commit()
            return r.id

    @app.get("/health")
    def health():
        return {"status": "ok", "llm_enabled": llm.enabled()}

    @app.post("/review/diff")
    def review_text(b: DiffIn, o: str = Depends(owner)):
        reviewer, f = run_review(b.diff)
        return {"id": save(o, "pasted diff", reviewer, f), "reviewer": reviewer, "findings": [x.dict() for x in f]}

    @app.post("/review/pr")
    def review_pr(b: PrIn, o: str = Depends(owner)):
        try:
            own, repo, n = github.parse_pr_url(b.url)
            diff = github.fetch_diff(own, repo, n)
        except ValueError as e:
            raise HTTPException(422, str(e))
        except LookupError as e:
            raise HTTPException(404, str(e))
        except Exception:
            raise HTTPException(502, "Could not fetch the PR from GitHub (rate limit or network)")
        reviewer, f = run_review(diff)
        return {"id": save(o, b.url, reviewer, f), "reviewer": reviewer, "findings": [x.dict() for x in f]}

    @app.get("/reviews")
    def reviews(o: str = Depends(owner)):
        with D.Session() as s:
            rows = s.query(D.Review).filter_by(owner=o).order_by(D.Review.id.desc()).limit(20).all()
            return [{"id": r.id, "source": r.source, "reviewer": r.reviewer, "count": len(r.findings), "created": r.created.isoformat()} for r in rows]

    @app.get("/samples")
    def samples():
        return [{"id": c["id"], "title": c["title"], "kind": c["kind"], "diff": diff_for(c)} for c in CASES]

    @app.get("/benchmark")
    def benchmark():
        return evaluate()  # runs the real rules on the bundled PRs each time

    return app


app = create_app()
