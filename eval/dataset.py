"""Benchmark: 40 synthetic PRs (20 pattern bugs, 8 logic bugs, 12 clean) written by hand. Each has a before/after file; the diff is generated with difflib.
kind: 'pattern'  = bug is a well-known pattern (rules are designed for these)
      'logic'    = real logic bug with no pattern (rules are NOT expected to catch these)
      'clean'    = correct change, includes look-alikes meant to trigger false positives
bugs: list of (substring of the buggy added line, category). The expected line is found in the AFTER file.
CAVEAT: the same person wrote the rules and this set, so pattern recall is optimistic."""
import difflib

BASE = "import os\nimport sqlite3\n\n\ndef helper(x):\n    return x * 2\n"

P = lambda id, title, add, bugs: dict(id=id, title=title, kind="pattern", before=BASE, after=BASE + "\n\n" + add, bugs=bugs)
L = lambda id, title, add, bugs: dict(id=id, title=title, kind="logic", before=BASE, after=BASE + "\n\n" + add, bugs=bugs)
C = lambda id, title, add: dict(id=id, title=title, kind="clean", before=BASE, after=BASE + "\n\n" + add, bugs=[])

CASES = [
    P("p01", "Add tag collector", "def collect(item, tags=[]):\n    tags.append(item)\n    return tags\n", [("tags=[]", "mutable-default")]),
    P("p02", "Cache user lookups", "def cached(key, cache={}):\n    return cache.setdefault(key, helper(key))\n", [("cache={}", "mutable-default")]),
    P("p03", "Parse config", "def parse(s):\n    try:\n        return int(s)\n    except:\n        return 0\n", [("except:", "bare-except")]),
    P("p04", "Safe int", "def safe(s):\n    try:\n        return int(s)\n    except Exception:\n        pass\n    return None\n", [("pass", "swallowed-exception")]),
    P("p05", "Null check", "def has_user(u):\n    return u != None\n", [("u != None", "none-compare")]),
    P("p06", "User search", "def find(db, name):\n    cur = db.cursor()\n    cur.execute(f\"SELECT * FROM users WHERE name = '{name}'\")\n    return cur.fetchall()\n", [("cur.execute(f", "sql-injection")]),
    P("p07", "Delete user", "def delete(db, uid):\n    db.execute(\"DELETE FROM users WHERE id = %s\" % uid)\n", [("DELETE FROM", "sql-injection")]),
    P("p08", "Order lookup", "def order(db, oid):\n    return db.execute(\"SELECT * FROM orders WHERE id = \" + oid).fetchone()\n", [("SELECT * FROM orders", "sql-injection")]),
    P("p09", "Payment client", "API_KEY = \"sk_live_51Habcdef123456\"\n\n\ndef headers():\n    return {\"Authorization\": API_KEY}\n", [("API_KEY =", "hardcoded-secret")]),
    P("p10", "DB connect", "def connect():\n    password = \"hunter2hunter2\"\n    return sqlite3.connect(\"app.db\", uri=bool(password))\n", [("password =", "hardcoded-secret")]),
    P("p11", "Calculator", "def calc(expr):\n    return eval(expr)\n", [("eval(expr)", "eval-exec")]),
    P("p12", "Run user script", "def run(code):\n    exec(code)\n", [("exec(code)", "eval-exec")]),
    P("p13", "Ping host", "import subprocess\n\n\ndef ping(host):\n    return subprocess.run(\"ping -c1 \" + host, shell=True)\n", [("shell=True", "shell-true")]),
    P("p14", "Load settings", "import yaml\n\n\ndef settings(text):\n    return yaml.load(text)\n", [("yaml.load(text)", "yaml-unsafe-load")]),
    P("p15", "Status check", "def is_done(status):\n    return status is \"done\"\n", [("status is", "is-literal")]),
    P("p16", "Dev server", "def main(app):\n    app.run(host=\"0.0.0.0\", debug=True)\n", [("debug=True", "debug-enabled")]),
    P("p17", "Read notes", "def notes(path):\n    f = open(path)\n    data = f.read()\n    return data\n", [("f = open", "unclosed-file")]),
    P("p18", "Fetch rates", "import requests\n\n\ndef rates():\n    return requests.get(\"https://api.example.com/rates\").json()\n", [("requests.get", "no-timeout")]),
    P("p19", "Two bugs in one PR", "def load(path, seen=[]):\n    f = open(path)\n    seen.append(path)\n    return f.read()\n", [("seen=[]", "mutable-default"), ("f = open", "unclosed-file")]),
    P("p20", "Webhook post", "import requests\n\n\ndef notify(url, payload):\n    return requests.post(url, json=payload)\n", [("requests.post", "no-timeout")]),
    L("l01", "Average", "def average(xs):\n    return sum(xs) // len(xs)\n", [("sum(xs) // len", "logic")]),
    L("l02", "Pairs", "def pairs(xs):\n    return [(xs[i], xs[i + 1]) for i in range(len(xs))]\n", [("range(len(xs))", "logic")]),
    L("l03", "Page slice", "def page(items, n, size):\n    return items[n * size : n * size + size - 1]\n", [("size - 1", "logic")]),
    L("l04", "Discount", "def discount(price, pct):\n    return price - price * pct\n", [("price - price * pct", "logic")]),
    L("l05", "Adult check", "def is_adult(age):\n    return age > 18\n", [("age > 18", "logic")]),
    L("l06", "Max of list", "def biggest(xs):\n    best = 0\n    for x in xs:\n        if x > best:\n            best = x\n    return best\n", [("best = 0", "logic")]),
    L("l07", "Swap args", "def transfer(db, src, dst, amount):\n    db.debit(dst, amount)\n    db.credit(src, amount)\n", [("db.debit(dst", "logic")]),
    L("l08", "Retry loop", "def retry(fn, n=3):\n    for i in range(n):\n        r = fn()\n        if r:\n            return r\n        return None\n", [("return None", "logic")]),
    C("c01", "Specific except", "def parse(s):\n    try:\n        return int(s)\n    except ValueError:\n        return 0\n"),
    C("c02", "None identity", "def has_user(u):\n    return u is not None\n"),
    C("c03", "Parameterized query", "def find(db, name):\n    cur = db.cursor()\n    cur.execute(\"SELECT * FROM users WHERE name = ?\", (name,))\n    return cur.fetchall()\n"),
    C("c04", "Secret from env", "def key():\n    return os.environ[\"API_KEY\"]\n\n\ndef token_name():\n    token = os.getenv(\"TOKEN_NAME\", \"default\")\n    return token\n"),
    C("c05", "File with context manager", "def notes(path):\n    with open(path) as f:\n        return f.read()\n"),
    C("c06", "Timeout set (multi-line)", "import requests\n\n\ndef rates():\n    return requests.get(\n        \"https://api.example.com/rates\",\n        timeout=5,\n    ).json()\n"),
    C("c07", "Safe subprocess", "import subprocess\n\n\ndef ping(host):\n    return subprocess.run([\"ping\", \"-c1\", host], check=True)\n"),
    C("c08", "literal_eval and safe_load", "import ast\nimport yaml\n\n\ndef parse(s):\n    return ast.literal_eval(s)\n\n\ndef settings(text):\n    return yaml.safe_load(text)\n"),
    C("c09", "Constant table name in SQL (safe, but looks risky)", "TABLE = \"users\"\n\n\ndef count(db):\n    return db.execute(f\"SELECT COUNT(*) FROM {TABLE}\").fetchone()[0]\n"),
    C("c10", "Mutable default avoided", "def collect(item, tags=None):\n    tags = [] if tags is None else tags\n    tags.append(item)\n    return tags\n"),
    C("c11", "Doc mentions bad patterns", "def note():\n    # never use eval(x) or except: pass, see docs\n    return \"use yaml.safe_load, not yaml.load(text)\"\n"),
    C("c12", "Keyword passed to class", "def build(cls):\n    return cls(password_hint=\"Use at least 12 characters\")\n"),
]


def diff_for(case) -> str:
    a, b = case["before"].splitlines(keepends=True), case["after"].splitlines(keepends=True)
    return "".join(difflib.unified_diff(a, b, "a/app.py", "b/app.py", n=3))


def expected(case):
    """-> [(path, line_no, category)] from the AFTER file."""
    lines = case["after"].splitlines()
    out = []
    for sub, cat in case["bugs"]:
        for i, ln in enumerate(lines, 1):
            if sub in ln and ln not in case["before"]:
                out.append(("app.py", i, cat)); break
        else:
            raise ValueError(f"{case['id']}: marker {sub!r} not found")
    return out
