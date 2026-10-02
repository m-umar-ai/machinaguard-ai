"""MachinaGuard FINAL READINESS CHECK.
Run from the project folder (the one with app.py):   python final_check.py
Prints PASS / WARN / FAIL / SKIP for every check. It never prints a full API key and never sends a Telegram message."""
import json, os, re, subprocess, sys, time, urllib.error, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT); sys.path.insert(0, str(ROOT))
try:
    from dotenv import load_dotenv; load_dotenv(ROOT / ".env")
except Exception:
    pass

RESULTS = []
KEY_NAMES = ("GEMINI_API_KEY", "OPENAI_API_KEY", "TELEGRAM_BOT_TOKEN")
HINTS = {401: "key invalid or revoked - create a new one", 403: "key blocked or has no access", 404: "model name wrong or retired - change the *_MODEL line in .env",
         429: "quota / rate limit reached - wait, or use the other provider", 503: "provider busy - try again in a minute"}


def check(name):
    def deco(fn):
        try:
            status, detail = fn()
        except Exception as e:
            status, detail = "FAIL", f"{type(e).__name__}: {str(e)[:200]}"
        RESULTS.append((name, status, detail)); print(f"[{status:4}] {name}: {detail}", flush=True)
        return fn
    return deco


def http(url, payload=None, headers=None, timeout=40, method=None):
    h = {"User-Agent": "MachinaGuard-check/1.0", "Content-Type": "application/json"}; h.update(headers or {})
    for attempt in range(2):
        req = urllib.request.Request(url, data=json.dumps(payload).encode() if payload is not None else None, headers=h, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            body = ""
            try: body = e.read().decode()[:160]
            except Exception: pass
            if e.code == 503 and attempt == 0:
                time.sleep(4); continue
            return e.code, body
        except Exception as e:
            return 0, f"{type(e).__name__}: {e}"
    return 0, "unreachable"


def hint(code, body):
    if code == 0: return f"no connection ({body})"
    extra = " (blocked by Cloudflare)" if "1010" in str(body) else ""
    return f"HTTP {code}: {HINTS.get(code, 'unexpected error')}{extra}"


SAVED_ENV = {k: os.environ[k] for k in KEY_NAMES + ("LLM_PROVIDER", "GEMINI_MODEL", "OPENAI_MODEL", "OPENAI_BASE_URL") if k in os.environ}
print("MachinaGuard final check - folder:", ROOT, "\n")


@check("1. Python packages")
def _():
    missing = []
    for mod in ("streamlit", "pandas", "numpy", "sklearn", "plotly", "faiss", "joblib", "dotenv", "pytest"):
        try: __import__(mod)
        except Exception: missing.append(mod)
    py = f"Python {sys.version_info.major}.{sys.version_info.minor}"
    return ("FAIL", f"{py}; missing: {', '.join(missing)}  ->  run: pip install -r requirements.txt") if missing else ("PASS", f"{py}; all packages found")


@check("2. .env file format")
def _():
    p = ROOT / ".env"
    if not p.exists(): return "SKIP", "no .env file (app runs in OFFLINE mode)"
    bad, seen = [], []
    for i, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        s = line.strip()
        if not s or s.startswith("#"): continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(\S*)$", s)
        if not m: bad.append(i); continue
        k, v = m.groups(); seen.append(f"{k}({'set, %d chars' % len(v) if v else 'EMPTY'})")
    if bad: return "FAIL", f"line(s) {bad} are not KEY=VALUE (no spaces, no quotes). Found: {', '.join(seen)}"
    return "PASS", ", ".join(seen) or "file is empty"


@check("3. No API key leaked into project files")
def _():
    skip_dirs = {".venv", "venv", "__pycache__", ".git", ".pytest_cache", "models", "node_modules"}
    pats = [re.compile(r"gsk_[A-Za-z0-9]{20,}"), re.compile(r"AIza[0-9A-Za-z_\-]{30,}"), re.compile(r"AQ\.[A-Za-z0-9_\-]{30,}"), re.compile(r"\b\d{8,10}:[A-Za-z0-9_\-]{30,}")]
    secrets = [v for k, v in SAVED_ENV.items() if k in KEY_NAMES and len(v) >= 20]
    hits = []
    for p in ROOT.rglob("*"):
        if p.is_dir() or any(part in skip_dirs for part in p.relative_to(ROOT).parts) or p.name == ".env" or p.suffix in {".joblib", ".png", ".zip", ".pyc", ".faiss"}: continue
        try: t = p.read_text(encoding="utf-8")
        except Exception: continue
        if any(x.search(t) for x in pats) or any(s in t for s in secrets): hits.append(str(p.relative_to(ROOT)))
    return ("FAIL", f"key-like text found in: {', '.join(hits)}  ->  remove it before sharing / pushing to GitHub") if hits else ("PASS", "no keys found outside .env")


@check("4. .env is git-ignored")
def _():
    g = ROOT / ".gitignore"
    ok = g.exists() and any(l.strip() in (".env", "/.env", ".env*") for l in g.read_text().splitlines())
    return ("PASS", ".gitignore lists .env") if ok else ("FAIL", "add a line  .env  to .gitignore so keys never reach GitHub")


@check("5. Gemini key (direct call)")
def _():
    k = SAVED_ENV.get("GEMINI_API_KEY")
    if not k: return "SKIP", "no GEMINI_API_KEY"
    model = SAVED_ENV.get("GEMINI_MODEL", "gemini-3.8-flash")
    code, body = http(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent", {"contents": [{"parts": [{"text": "Reply with: OK"}]}]}, {"x-goog-api-key": k})
    return ("PASS", f"model {model} answered") if code == 200 else ("FAIL", f"model {model}: {hint(code, body)}")


@check("6. Groq / OpenAI-compatible key (direct call)")
def _():
    k = SAVED_ENV.get("OPENAI_API_KEY")
    if not k: return "SKIP", "no OPENAI_API_KEY"
    base = SAVED_ENV.get("OPENAI_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/"); model = SAVED_ENV.get("OPENAI_MODEL", "openai/gpt-oss-120b")
    code, body = http(f"{base}/chat/completions", {"model": model, "messages": [{"role": "user", "content": "Reply with: OK"}], "max_tokens": 200}, {"Authorization": "Bearer " + k})
    if code == 200: return "PASS", f"model {model} answered"
    if code == 404 and "groq" in base:
        c2, b2 = http(f"{base}/models", headers={"Authorization": "Bearer " + k}, method="GET")
        if c2 == 200: return "FAIL", f"model {model} not available; models you can use: " + ", ".join(m["id"] for m in b2["data"] if "whisper" not in m["id"] and "orpheus" not in m["id"] and "guard" not in m["id"])[:300]
    return "FAIL", f"model {model}: {hint(code, body)}"


@check("7. App LLM path (utils.config.llm_text)")
def _():
    from utils import config as c
    prov = c.llm_provider()
    if prov is None: return "SKIP", "no key configured - OFFLINE mode"
    out = c.llm_text("Reply with exactly: OK")
    if out: return "PASS", f"provider {prov} / {c.llm_name()} replied: {out[:30]!r}"
    return "FAIL", f"provider {prov} returned nothing. Reason: {getattr(c, 'LAST_LLM_ERROR', None) or 'unknown'}"


@check("8. Telegram bot token (getMe only, sends nothing)")
def _():
    t = SAVED_ENV.get("TELEGRAM_BOT_TOKEN")
    if not t or not os.getenv("TELEGRAM_CHAT_ID"): return "SKIP", "Telegram not configured (optional)"
    code, body = http(f"https://api.telegram.org/bot{t}/getMe", method="GET")
    return ("PASS", "bot token valid") if code == 200 else ("FAIL", hint(code, body))


@check("9. Full test suite (pytest)")
def _():
    r = subprocess.run([sys.executable, "-m", "pytest", "-q"], capture_output=True, text=True, timeout=900)
    tail = " | ".join([l for l in (r.stdout + r.stderr).strip().splitlines() if l.strip()][-2:])
    return ("PASS", tail) if r.returncode == 0 else ("FAIL", tail + "   (run  python -m pytest -q  to see details)")


@check("10. Offline end-to-end: failure -> approval -> work order")
def _():
    for k in KEY_NAMES + ("LLM_PROVIDER",): os.environ.pop(k, None)   # deterministic: no live LLM in this check
    from core import MachineSession
    s = MachineSession(); s.simulate_failure()
    for _i in range(150):
        s.tick()
        if s.incident and s.incident["reveal"] >= len(s.incident["result"]["events"]): break
    if not s.incident: return "FAIL", "no incident was raised"
    if s.incident["workflow"]["ticket"] is not None: return "FAIL", "work order created BEFORE human approval"
    s.approve(); t = s.incident["workflow"]["ticket"]
    return ("PASS", f"incident raised, human gate respected, work order {t['ticket_id']} created after approval") if t else ("FAIL", "no work order after approval")


@check("11. Ask the Machine really uses the LLM")
def _():
    os.environ.update(SAVED_ENV)
    if not any(SAVED_ENV.get(k) for k in ("GEMINI_API_KEY", "OPENAI_API_KEY")): return "SKIP", "no key - OFFLINE mode"
    from core import MachineSession
    from genai.assistant import ask
    s = MachineSession()
    a = ask("What is bearing degradation and what should I check first?", s.engine.frame(120), s.detector, s.kb, s._trend())
    if a["method"].startswith("LLM"): return "PASS", a["method"]
    return "WARN", f"fell back to '{a['method']}' - reason: {a.get('llm_error') or 'not reported'} (app still works offline)"


print("\n" + "=" * 70)
n = {k: sum(1 for _, s, _ in RESULTS if s == k) for k in ("PASS", "WARN", "FAIL", "SKIP")}
print(f"SUMMARY: {n['PASS']} passed, {n['WARN']} warnings, {n['FAIL']} failed, {n['SKIP']} skipped")
print("READY FOR DEMO" if n["FAIL"] == 0 else "NOT READY - fix the [FAIL] lines above, then run this again")
sys.exit(1 if n["FAIL"] else 0)
