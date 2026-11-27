import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import { App } from "./App";

const samples = [{ id: "p06", title: "User search", kind: "pattern", diff: "--- a/app.py\n+++ b/app.py\n@@ -1,1 +1,2 @@\n x\n+cur.execute(f\"...\")\n" }];

test("Review sample reviews the sample and flags the vulnerable line", async () => {
  vi.stubGlobal("fetch", vi.fn(async (full: string, init?: RequestInit) => {
    const url = full.replace(/^\/api/, "");
    if (url === "/samples") return { ok: true, status: 200, json: async () => samples } as Response;
    if (url === "/reviews") return { ok: true, status: 200, json: async () => [] } as Response;
    if (url === "/review/diff" && init?.method === "POST")
      return { ok: true, status: 200, json: async () => ({ id: 1, reviewer: "rules", findings: [{ file: "app.py", line: 2, category: "sql-injection", severity: "high", message: "SQL built by string formatting.", source: "rules" }] }) } as Response;
    return { ok: false, status: 404, statusText: "nf", json: async () => ({}) } as Response;
  }));
  render(<App />);
  const btn = await screen.findByText("Review sample PR");
  await waitFor(() => expect(btn).toBeEnabled());
  await userEvent.click(btn);
  expect((await screen.findAllByText("app.py:2")).length).toBeGreaterThan(0);
  expect(screen.getAllByText("sql-injection").length).toBeGreaterThan(0);
  expect(screen.getAllByText(/1 finding/).length).toBeGreaterThan(0);
});

test("shows API errors", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => ({ ok: false, status: 500, statusText: "boom", json: async () => ({ detail: "db down" }) }) as Response));
  render(<App />);
  expect(await screen.findByRole("alert")).toHaveTextContent("db down");
});
