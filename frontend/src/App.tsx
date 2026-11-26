import { useEffect, useState } from "react";
import { api, Bench, Finding, Sample } from "./api";

type Tab = "review" | "benchmark";

export function App() {
  const [tab, setTab] = useState<Tab>("review");
  const [samples, setSamples] = useState<Sample[]>([]);
  const [diff, setDiff] = useState(""); const [url, setUrl] = useState("");
  const [findings, setFindings] = useState<Finding[] | null>(null); const [reviewer, setReviewer] = useState("");
  const [bench, setBench] = useState<Bench | null>(null);
  const [err, setErr] = useState(""); const [busy, setBusy] = useState(false);
  const [history, setHistory] = useState<{ id: number; source: string; count: number }[]>([]);

  const loadHistory = () => api.history().then(setHistory).catch(() => undefined);
  useEffect(() => { api.samples().then(setSamples).catch((e) => setErr(e.message)); loadHistory(); }, []);
  useEffect(() => { if (tab === "benchmark" && !bench) api.benchmark().then(setBench).catch((e) => setErr(e.message)); }, [tab, bench]);

  const run = async (fn: () => Promise<{ reviewer: string; findings: Finding[] }>) => {
    setBusy(true); setErr("");
    try { const r = await fn(); setFindings(r.findings); setReviewer(r.reviewer); loadHistory(); } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  };
  const tryDemo = () => {
    const s = samples.find((x) => x.id === "p06") ?? samples[0];
    if (!s) return;
    setDiff(s.diff); run(() => api.review(s.diff));
  };
  const flagged = new Map((findings ?? []).map((f) => [f.line, f]));
  // Track the new-file line number for each diff row so flagged lines can be highlighted.
  const rows: { text: string; line?: number }[] = []; let n = 0;
  for (const t of diff.split("\n")) {
    const h = /^@@ -\d+(?:,\d+)? \+(\d+)/.exec(t);
    if (h) { n = Number(h[1]); rows.push({ text: t }); continue; }
    if (t.startsWith("+++") || t.startsWith("---")) { rows.push({ text: t }); continue; }
    if (t.startsWith("-")) { rows.push({ text: t }); continue; }
    rows.push({ text: t, line: n }); n++;
  }

  return (
    <div className="app">
      <header><h1>AI Code Review Assistant</h1><span className="badge">DEMO: no LLM key is configured, so the rule-based reviewer runs</span></header>
      <nav><button className={tab === "review" ? "on" : ""} onClick={() => setTab("review")}>Review</button><button className={tab === "benchmark" ? "on" : ""} onClick={() => setTab("benchmark")}>Benchmark</button></nav>
      {err && <div className="err" role="alert">{err}</div>}

      {tab === "review" && (<section>
        <div className="card">
          <button className="primary" disabled={busy || !samples.length} onClick={tryDemo}>Try demo</button>
          <select value="" onChange={(e) => { const s = samples.find((x) => x.id === e.target.value); if (s) { setDiff(s.diff); setFindings(null); } }}>
            <option value="">Load a benchmark PR...</option>{samples.map((s) => <option key={s.id} value={s.id}>{s.id} {s.title} ({s.kind})</option>)}</select>
          <div><input style={{ width: "60%" }} placeholder="https://github.com/owner/repo/pull/123 (public PRs)" value={url} onChange={(e) => setUrl(e.target.value)} />
            <button disabled={busy || !url} onClick={() => run(() => api.reviewPr(url))}>Review PR</button></div>
          <textarea rows={8} placeholder="...or paste a unified diff here" value={diff} onChange={(e) => setDiff(e.target.value)} />
          <button disabled={busy || !diff.trim()} onClick={() => run(() => api.review(diff))}>Review pasted diff</button>
        </div>
        {findings && (<div className="card"><h3>{findings.length} finding(s) <small>reviewer: {reviewer}</small></h3>
          {findings.length === 0 && <p>No issues found by the rules. This does not mean the code is correct: the rules do not catch logic bugs.</p>}
          {findings.map((f, i) => <div key={i} className={`f ${f.severity}`}><b>{f.file}:{f.line}</b> <span className="cat">{f.category}</span> <span>{f.severity}</span><div>{f.message}</div></div>)}</div>)}
        {diff && (<div className="card"><h3>Diff</h3><pre className="diff">{rows.map((r, i) => <div key={i} className={r.text.startsWith("+") && !r.text.startsWith("+++") ? (r.line !== undefined && flagged.has(r.line) ? "add flag" : "add") : r.text.startsWith("-") ? "del" : ""}>{r.text || " "}</div>)}</pre></div>)}
        {history.length > 0 && <div className="card"><h3>Your recent reviews (saved in PostgreSQL)</h3>{history.map((h) => <div key={h.id}>#{h.id} {h.source}: {h.count} finding(s)</div>)}</div>}
      </section>)}

      {tab === "benchmark" && (<section>{!bench ? <p>Running the reviewer on the benchmark...</p> : (<>
        <div className="card"><h3>Measured on {bench.prs} synthetic PRs ({bench.prs_with_bugs} with known bugs, {bench.clean_prs} clean)</h3>
          <div className="kpis"><div><small>Detection rate (all bugs)</small><b>{(bench.detection_rate * 100).toFixed(1)}%</b> <small>{bench.detected}/{bench.bugs}</small></div>
            <div><small>Pattern bugs</small><b>{(bench.by_kind.pattern.rate * 100).toFixed(0)}%</b> <small>{bench.by_kind.pattern.found}/{bench.by_kind.pattern.bugs}</small></div>
            <div><small>Logic bugs</small><b>{(bench.by_kind.logic.rate * 100).toFixed(0)}%</b> <small>{bench.by_kind.logic.found}/{bench.by_kind.logic.bugs}</small></div>
            <div><small>False positives</small><b>{bench.false_positives}</b> <small>on {bench.clean_prs_with_false_positive} of {bench.clean_prs} clean PRs</small></div></div>
          <p><small>Rules and benchmark were written by the same person, so the pattern score is optimistic. The logic score shows what pattern rules cannot do.</small></p></div>
        <div className="card"><h3>False positives</h3>{bench.false_positive_list.map((f, i) => <div key={i}>{f.case} {f.title}: flagged {f.category} at line {f.line}</div>)}</div>
        <div className="card"><h3>Per PR</h3><table><thead><tr><th>PR</th><th>Title</th><th>Kind</th><th>Bugs</th><th>Found</th><th>FP</th></tr></thead><tbody>
          {bench.rows.map((r) => <tr key={r.id}><td>{r.id}</td><td>{r.title}</td><td>{r.kind}</td><td>{r.expected}</td><td>{r.found}</td><td>{r.false_positives}</td></tr>)}</tbody></table></div></>)}</section>)}
    </div>
  );
}
