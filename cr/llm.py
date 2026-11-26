"""Optional LLM reviewer (OpenAI-compatible chat API). WRITTEN BUT NEVER RUN: no API key was available when this was built.
Enabled only when OPENAI_API_KEY is set. Its findings are tagged source='llm'."""
import json
import os
import httpx
from .rules import Finding

PROMPT = ("You review a unified diff. Report only real bugs in ADDED lines, no style nits. "
          'Reply with JSON: {"findings":[{"file":str,"line":int,"category":str,"severity":"low|medium|high","message":str}]}. '
          "The line is the line number in the new file. If there are no bugs reply {\"findings\":[]}.")


def enabled() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))


def review_diff(diff: str) -> list[Finding]:  # pragma: no cover (needs a key)
    r = httpx.post(os.getenv("LLM_BASE_URL", "https://api.openai.com/v1") + "/chat/completions", timeout=90,
                   headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
                   json={"model": os.getenv("LLM_MODEL", "gpt-4o-mini"), "temperature": 0, "response_format": {"type": "json_object"},
                         "messages": [{"role": "system", "content": PROMPT}, {"role": "user", "content": diff[:60000]}]})
    r.raise_for_status()
    data = json.loads(r.json()["choices"][0]["message"]["content"])
    return [Finding(f["file"], int(f["line"]), str(f.get("category", "llm")), f.get("severity", "medium"), f["message"], "llm") for f in data.get("findings", [])]
