"""Run the reviewer on every benchmark PR and measure it. Numbers come from this real run, no tuning of the dataset after seeing results."""

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from cr.rules import review_diff
from eval.dataset import CASES, diff_for, expected


def evaluate(reviewer=review_diff):
    rows, tp, fp, fn = [], 0, 0, 0
    by_kind = {k: {"bugs": 0, "found": 0} for k in ("pattern", "logic")}
    fp_list = []
    cat = {}

    def bump(k, f):
        cat.setdefault(k, {"tp": 0, "fp": 0, "fn": 0})[f] += 1

    clean_with_fp = 0
    for c in CASES:
        exp = expected(c)
        got = reviewer(diff_for(c))
        matched = set()
        for f in got:
            hit = next(
                (e for e in exp if e[1] == f.line and e[2] == f.category and e not in matched), None
            )
            if hit:
                matched.add(hit)
                tp += 1
                bump(f.category, "tp")
            else:
                fp += 1
                bump(f.category, "fp")
                fp_list.append(
                    {"case": c["id"], "title": c["title"], "line": f.line, "category": f.category}
                )
        fn += len(exp) - len(matched)
        for e in exp:
            if e not in matched:
                bump(e[2], "fn")
        if c["kind"] in by_kind:
            by_kind[c["kind"]]["bugs"] += len(exp)
            by_kind[c["kind"]]["found"] += len(matched)
        if c["kind"] == "clean" and any(x["case"] == c["id"] for x in fp_list):
            clean_with_fp += 1
        rows.append(
            {
                "id": c["id"],
                "title": c["title"],
                "kind": c["kind"],
                "expected": len(exp),
                "found": len(matched),
                "false_positives": len([x for x in fp_list if x["case"] == c["id"]]),
            }
        )
    bugs = tp + fn
    per_category = {}
    for k, v in sorted(cat.items()):
        pr = v["tp"] / (v["tp"] + v["fp"]) if v["tp"] + v["fp"] else None
        rc = v["tp"] / (v["tp"] + v["fn"]) if v["tp"] + v["fn"] else None
        f1 = 2 * pr * rc / (pr + rc) if pr and rc else None
        per_category[k] = {**v, "precision": None if pr is None else round(pr, 3),
                           "recall": None if rc is None else round(rc, 3), "f1": None if f1 is None else round(f1, 3)}
    prs_with_bug = [r for r in rows if r["expected"]]
    return {
        "prs": len(CASES),
        "prs_with_bugs": len(prs_with_bug),
        "clean_prs": len([c for c in CASES if c["kind"] == "clean"]),
        "bugs": bugs,
        "detected": tp,
        "detection_rate": round(tp / bugs, 3),
        "pr_fully_detected": len([r for r in prs_with_bug if r["found"] == r["expected"]]),
        "by_kind": {k: {**v, "rate": round(v["found"] / v["bugs"], 3)} for k, v in by_kind.items()},
        "false_positives": fp,
        "precision": round(tp / (tp + fp), 3) if tp + fp else None,
        "clean_prs_with_false_positive": clean_with_fp,
        "per_category": per_category,
        "false_positive_list": fp_list,
        "rows": rows,
    }


if __name__ == "__main__":
    r = evaluate()
    out = pathlib.Path(__file__).with_name("results.json")
    out.write_text(json.dumps(r, indent=1))
    print(json.dumps({k: v for k, v in r.items() if k not in ("rows",)}, indent=1))
