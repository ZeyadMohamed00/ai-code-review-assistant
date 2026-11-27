import { useEffect, useMemo, useState } from "react";
import { api, type Bench, type Finding, type Sample } from "./api";
import { Badge, Bar, Donut, Empty, Shell, Skeleton, Stat, Tabs, ToastProvider, useToast } from "./ui";

type Page = "review" | "benchmark" | "history";
type Result = { id: number; reviewer: string; findings: Finding[]; diff: string; source: string };
const sevKind = (s: string) => (s === "high" ? "bad" : s === "medium" ? "warn" : "info") as "bad" | "warn" | "info";
const KEY = "cr_results_v1";
const loadStore = (): Record<number, Result> => { try { return JSON.parse(localStorage.getItem(KEY) ?? "{}"); } catch { return {}; } };

export function App() { return <ToastProvider><Main /></ToastProvider>; }

function Main() {
  const toast = useToast();
  const [page, setPage] = useState<Page>("review");
  const [samples, setSamples] = useState<Sample[]>([]);
  const [result, setResult] = useState<Result | null>(null);
  const [history, setHistory] = useState<{ id: number; source: string; reviewer: string; count: number; created: string }[]>([]);
  const [err, setErr] = useState("");
  const loadHistory = () => api.history().then(setHistory).catch(() => undefined);
  useEffect(() => { api.samples().then(setSamples).catch((e) => { setErr(e.message); toast(e.message, "bad"); }); loadHistory(); }, []);
  const save = (r: Result) => { const st = loadStore(); st[r.id] = r; const keys = Object.keys(st).map(Number).sort((a, b) => b - a).slice(0, 20); const out: Record<number, Result> = {}; keys.forEach((k) => { out[k] = st[k]; }); try { localStorage.setItem(KEY, JSON.stringify(out)); } catch { /* quota */ } };
  const onResult = (r: Result) => { setResult(r); save(r); loadHistory(); };
  return (
    <Shell brand="ReviewBot" tagline="Diff review assistant" page={page} onNav={(p) => setPage(p as Page)}
      nav={[{ id: "review", label: "Review", icon: "✎" }, { id: "benchmark", label: "Benchmark", icon: "▦" }, { id: "history", label: "History", icon: "☰", badge: history.length || undefined }]}
      footer={<div className="muted small">Rule-based reviewer. No LLM is configured.</div>}>
      {err && <div className="card" role="alert" style={{ borderColor: "#ef4444", marginBottom: 12 }}>{err}</div>}
      {page === "review" && <Review samples={samples} result={result} onResult={onResult} />}
      {page === "benchmark" && <Benchmark />}
      {page === "history" && <History history={history} open={(id) => { const r = loadStore()[id]; if (r) { setResult(r); setPage("review"); } else toast("This review was made in another browser session, so only its summary is available.", "bad"); }} />}
    </Shell>
  );
}

function Review({ samples, result, onResult }: { samples: Sample[]; result: Result | null; onResult: (r: Result) => void }) {
  const toast = useToast();
  const [mode, setMode] = useState<"paste" | "pr" | "sample">("paste");
  const [diff, setDiff] = useState(""); const [url, setUrl] = useState(""); const [busy, setBusy] = useState(false);
  const [sev, setSev] = useState<"all" | "high" | "medium" | "low">("all");
  useEffect(() => { if (result) setDiff(result.diff); }, [result]);
  const run = async (fn: () => Promise<{ id: number; reviewer: string; findings: Finding[] }>, d: string, source: string) => {
    setBusy(true);
    try { const r = await fn(); onResult({ ...r, diff: d, source }); setDiff(d); toast(`${r.findings.length} finding(s)`); } catch (e) { toast((e as Error).message, "bad"); } finally { setBusy(false); }
  };
  const reviewSample = () => { const s = samples.find((x) => x.id === "p06") ?? samples[0]; if (s) { setDiff(s.diff); run(() => api.review(s.diff), s.diff, `sample ${s.id}`); } };
  const findings = result?.findings ?? [];
  const shown = findings.filter((f) => sev === "all" || f.severity === sev);
  const bySev = useMemo(() => { const m: Record<string, number> = {}; findings.forEach((f) => { m[f.severity] = (m[f.severity] ?? 0) + 1; }); return m; }, [findings]);
  const byFile = useMemo(() => { const m: Record<string, number> = {}; findings.forEach((f) => { m[f.file] = (m[f.file] ?? 0) + 1; }); return Object.entries(m); }, [findings]);
  const md = () => `# Code review (${result?.reviewer})\n\n${findings.map((f) => `- **${f.file}:${f.line}** [${f.severity}] ${f.category}: ${f.message}`).join("\n") || "No findings."}\n`;
  // Map each diff row to its file and new-file line so findings can be shown inline.
  const rows = useMemo(() => {
    const out: { text: string; line?: number; file?: string }[] = []; let n = 0, file = "";
    for (const t of (result?.diff ?? diff).split("\n")) {
      const f = /^\+\+\+ b\/(.+)$/.exec(t); if (f) { file = f[1]; out.push({ text: t }); continue; }
      const h = /^@@ -\d+(?:,\d+)? \+(\d+)/.exec(t); if (h) { n = Number(h[1]); out.push({ text: t }); continue; }
      if (t.startsWith("+++") || t.startsWith("---") || t.startsWith("diff ") || t.startsWith("index ")) { out.push({ text: t }); continue; }
      if (t.startsWith("-")) { out.push({ text: t }); continue; }
      out.push({ text: t, line: n, file }); n++;
    }
    return out;
  }, [result, diff]);
  return (
    <>
      <div className="page-h"><div><h1>Review a pull request</h1><p>Flags likely bugs on the exact changed line. Paste a diff, load a sample, or give a public GitHub PR URL.</p></div>
        <div className="sp"><button className="btn primary" disabled={busy || !samples.length} onClick={reviewSample}>Review sample PR</button></div></div>
      <div className="grid g-main">
        <div className="card col"><Tabs tabs={[{ id: "paste" as const, label: "Paste diff" }, { id: "pr" as const, label: "GitHub PR" }, { id: "sample" as const, label: "Samples" }]} value={mode} onChange={setMode} />
          {mode === "paste" && <><textarea aria-label="Diff" className="code" placeholder="Paste a unified diff here" value={diff} onChange={(e) => setDiff(e.target.value)} /><button className="btn primary" disabled={busy || !diff.trim()} onClick={() => run(() => api.review(diff), diff, "pasted diff")}>{busy ? "Reviewing..." : "Review pasted diff"}</button></>}
          {mode === "pr" && <><input placeholder="https://github.com/owner/repo/pull/123 (public PRs)" value={url} onChange={(e) => setUrl(e.target.value)} /><button className="btn primary" disabled={busy || !url} onClick={() => run(() => api.reviewPr(url), "", url)}>Review PR</button><p className="muted small">Reads the public diff from GitHub (rate-limited, no token). Nothing is posted back to GitHub.</p></>}
          {mode === "sample" && <div className="list" style={{ maxHeight: 260, overflow: "auto" }}>{samples.map((s) => <div key={s.id} className="row" style={{ justifyContent: "space-between" }}><span>{s.id} {s.title} <Badge kind={s.kind === "logic" ? "warn" : "acc"}>{s.kind}</Badge></span><button className="btn" onClick={() => { setDiff(s.diff); setMode("paste"); }}>Load</button></div>)}</div>}
        </div>
        <div className="card col"><h3 style={{ margin: 0 }}>Summary</h3>
          {!result ? <p className="muted">Run a review to see findings.</p> : <>
            <div className="row"><Donut size={90} parts={[{ label: "high", value: bySev.high ?? 0, color: "#ef4444" }, { label: "medium", value: bySev.medium ?? 0, color: "#f59e0b" }, { label: "low", value: bySev.low ?? 0, color: "#3b82f6" }]} />
              <div className="col small"><span><b>{findings.length}</b> finding(s)</span><span className="muted">reviewer: {result.reviewer}</span>{byFile.map(([f, c]) => <span key={f} className="muted">{f}: {c}</span>)}</div></div>
            <div className="row"><button className="btn" onClick={() => { navigator.clipboard?.writeText(md()); toast("Review copied as Markdown"); }}>Copy as Markdown</button>
              <button className="btn" onClick={() => { const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([md()], { type: "text/markdown" })); a.download = "review.md"; a.click(); }}>Download .md</button></div></>}
        </div>
      </div>
      {result && (
        <>
          <div className="row" style={{ margin: "16px 0 8px" }}><h3 style={{ margin: 0 }}>{findings.length} finding(s)</h3>
            <Tabs tabs={(["all", "high", "medium", "low"] as const).map((t) => ({ id: t, label: t }))} value={sev} onChange={setSev} /></div>
          {findings.length === 0 && <Empty title="No issues found by the rules" hint="This does not mean the code is correct: pattern rules do not catch logic bugs." />}
          <div className="col">{shown.map((f, i) => <div key={i} className="card"><div className="row" style={{ justifyContent: "space-between" }}><b>{f.file}:{f.line}</b><span><Badge kind="acc">{f.category}</Badge> <Badge kind={sevKind(f.severity)}>{f.severity}</Badge></span></div><div className="muted" style={{ marginTop: 4 }}>{f.message}</div></div>)}</div>
          {result.diff && <><h3 style={{ margin: "16px 0 8px" }}>Diff with inline findings</h3>
            <div className="diffv">{rows.map((r, i) => { const hit = r.line !== undefined && r.text.startsWith("+") ? findings.filter((f) => f.line === r.line && (!r.file || f.file === r.file)) : [];
              return <div key={i}><div className={`dl ${r.text.startsWith("@@") ? "hunk" : r.text.startsWith("+") && !r.text.startsWith("+++") ? (hit.length ? "add flag" : "add") : r.text.startsWith("-") && !r.text.startsWith("---") ? "del" : ""}`}><span className="no">{r.line ?? ""}</span><span>{r.text || " "}</span></div>
                {hit.map((f, j) => <div key={j} className={`ann ${f.severity}`}><b>{f.category}</b> <Badge kind={sevKind(f.severity)}>{f.severity}</Badge><div>{f.message}</div></div>)}</div>; })}</div></>}
        </>
      )}
    </>
  );
}

function Benchmark() {
  const toast = useToast();
  const [bench, setBench] = useState<Bench | null>(null); const [kind, setKind] = useState<"all" | "pattern" | "logic" | "clean">("all");
  useEffect(() => { api.benchmark().then(setBench).catch((e) => toast(e.message, "bad")); }, []);
  if (!bench) return <><div className="page-h"><h1>Benchmark</h1></div><p className="muted">Running the reviewer on the benchmark...</p><Skeleton lines={4} /></>;
  const rows = bench.rows.filter((r) => kind === "all" || r.kind === kind);
  return (
    <>
      <div className="page-h"><div><h1>Benchmark</h1><p>Measured live on {bench.prs} synthetic PRs ({bench.prs_with_bugs} with known bugs, {bench.clean_prs} clean).</p></div></div>
      <div className="grid g4">
        <Stat label="Detection rate (all bugs)" value={`${(bench.detection_rate * 100).toFixed(1)}%`} hint={`${bench.detected}/${bench.bugs}`} />
        <Stat label="Pattern bugs" value={`${(bench.by_kind.pattern.rate * 100).toFixed(0)}%`} hint={`${bench.by_kind.pattern.found}/${bench.by_kind.pattern.bugs}`} />
        <Stat label="Logic bugs" value={`${(bench.by_kind.logic.rate * 100).toFixed(0)}%`} hint={`${bench.by_kind.logic.found}/${bench.by_kind.logic.bugs}`} />
        <Stat label="False positives" value={bench.false_positives} hint={`on ${bench.clean_prs_with_false_positive} of ${bench.clean_prs} clean PRs`} />
      </div>
      <div className="grid g2" style={{ marginTop: 16 }}>
        <div className="card col"><h3 style={{ margin: 0 }}>Detection by bug kind</h3>
          {(["pattern", "logic"] as const).map((k) => <div key={k}><div className="row" style={{ justifyContent: "space-between" }}><span>{k}</span><b>{bench.by_kind[k].found}/{bench.by_kind[k].bugs}</b></div><Bar pct={bench.by_kind[k].rate * 100} /></div>)}
          <div><div className="row" style={{ justifyContent: "space-between" }}><span>precision</span><b>{(bench.precision * 100).toFixed(1)}%</b></div><Bar pct={bench.precision * 100} /></div>
          <p className="muted small">Rules and benchmark were written by the same person, so the pattern score is optimistic. The logic score shows what pattern rules cannot do.</p></div>
        <div className="card"><h3>False positives</h3>{bench.false_positive_list.length === 0 && <p className="muted">None.</p>}{bench.false_positive_list.map((f, i) => <div key={i} style={{ padding: "6px 0" }}>{f.case} {f.title}: flagged <Badge kind="warn">{f.category}</Badge> at line {f.line}</div>)}</div>
      </div>
      <div className="card" style={{ marginTop: 16, overflowX: "auto" }}><div className="row" style={{ marginBottom: 8 }}><h3 style={{ margin: 0 }}>Per PR</h3><Tabs tabs={(["all", "pattern", "logic", "clean"] as const).map((t) => ({ id: t, label: t }))} value={kind} onChange={setKind} /></div>
        <table className="t"><thead><tr><th>PR</th><th>Title</th><th>Kind</th><th>Bugs</th><th>Found</th><th>FP</th></tr></thead><tbody>
          {rows.map((r) => <tr key={r.id}><td>{r.id}</td><td>{r.title}</td><td>{r.kind}</td><td>{r.expected}</td><td><Badge kind={r.expected && r.found < r.expected ? "bad" : r.expected ? "ok" : ""}>{r.found}</Badge></td><td>{r.false_positives || ""}</td></tr>)}</tbody></table></div>
    </>
  );
}

function History({ history, open }: { history: { id: number; source: string; reviewer: string; count: number; created: string }[]; open: (id: number) => void }) {
  return (
    <>
      <div className="page-h"><div><h1>History</h1><p>Your recent reviews, saved in PostgreSQL. Click one to reopen it if it was made in this browser.</p></div></div>
      {history.length === 0 ? <Empty title="No reviews yet" hint="Run a review first." /> : <div className="card" style={{ overflowX: "auto" }}><table className="t"><thead><tr><th>#</th><th>Source</th><th>Reviewer</th><th>Findings</th><th>When</th><th /></tr></thead><tbody>
        {history.map((h) => <tr key={h.id}><td>#{h.id}</td><td>{h.source}</td><td className="muted">{h.reviewer}</td><td><Badge kind={h.count ? "warn" : "ok"}>{h.count}</Badge></td><td className="muted">{h.created?.slice(0, 16).replace("T", " ")}</td><td><button className="btn" onClick={() => open(h.id)}>Open</button></td></tr>)}</tbody></table></div>}
    </>
  );
}
