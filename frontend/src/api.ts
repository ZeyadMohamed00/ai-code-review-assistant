export const API_BASE: string = import.meta.env.VITE_API_URL ?? (import.meta.env.DEV ? "/api" : "");

export function clientId(): string {
  let id = localStorage.getItem("cr_client_id");
  if (!id) {
    id = (crypto.randomUUID?.() ?? String(Date.now()) + Math.random().toString(16).slice(2)).replace(/[^a-zA-Z0-9-]/g, "");
    localStorage.setItem("cr_client_id", id);
  }
  return id;
}

async function raw(path: string, method = "GET", body?: unknown): Promise<Response> {
  const headers: Record<string, string> = { "X-Client-Id": clientId() };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const res = await fetch(API_BASE + path, { method, headers, body: body !== undefined ? JSON.stringify(body) : undefined });
  if (!res.ok) {
    let msg = res.statusText;
    try { const j = await res.json(); msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail); } catch { /* keep */ }
    throw new Error(msg);
  }
  return res;
}
async function req<T>(path: string, method = "GET", body?: unknown): Promise<T> {
  const r = await raw(path, method, body);
  return r.status === 204 ? (undefined as T) : r.json();
}

export type Finding = { file: string; line: number; category: string; severity: string; message: string; source: string };
export type Sample = { id: string; title: string; kind: string; diff: string };
export type Bench = { prs: number; prs_with_bugs: number; clean_prs: number; bugs: number; detected: number; detection_rate: number; precision: number; false_positives: number; clean_prs_with_false_positive: number;
  by_kind: Record<string, { bugs: number; found: number; rate: number }>; false_positive_list: { case: string; title: string; line: number; category: string }[]; rows: { id: string; title: string; kind: string; expected: number; found: number; false_positives: number }[] };

export const api = {
  samples: () => req<Sample[]>("/samples"),
  review: (diff: string) => req<{ id: number; reviewer: string; findings: Finding[] }>("/review/diff", "POST", { diff }),
  reviewPr: (url: string) => req<{ id: number; reviewer: string; findings: Finding[] }>("/review/pr", "POST", { url }),
  history: () => req<{ id: number; source: string; reviewer: string; count: number; created: string }[]>("/reviews"),
  benchmark: () => req<Bench>("/benchmark"),
};

