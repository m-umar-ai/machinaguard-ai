"""Find which Groq models work with MachinaGuard's agent protocol.
Run from the project folder:   python probe_models.py
Uses OPENAI_API_KEY / OPENAI_BASE_URL from .env. Never prints your key. Makes only a few tiny requests."""
import json, os, re, sys, time, urllib.error, urllib.request
from pathlib import Path
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except Exception:
    pass

KEY = os.getenv("OPENAI_API_KEY")
BASE = os.getenv("OPENAI_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
if not KEY:
    sys.exit("No OPENAI_API_KEY found in .env")

SYSTEM = ("You are an industrial investigator agent. Reply with ONE JSON object only, no other text. "
          'To use a tool reply {"thought": "...", "tool": "<name>", "args": {}}. '
          'To finish reply {"final": {"answer": "..."}}. Tools: run_anomaly_model, get_sensor_snapshot.')
USER = "Goal: find out whether the machine is healthy. Start by using a tool."


def call(path, payload=None):
    req = urllib.request.Request(BASE + path, data=json.dumps(payload).encode() if payload else None,
                                 headers={"Authorization": "Bearer " + KEY, "Content-Type": "application/json", "User-Agent": "MachinaGuard/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="replace")[:300]
    except Exception as e:
        return 0, f"{type(e).__name__}: {e}"[:300]


def parse(text):
    for cand in (text, (re.search(r"\{.*\}", text, re.S) or [None])[0] if re.search(r"\{.*\}", text, re.S) else None):
        if cand:
            try:
                obj = json.loads(cand)
                if isinstance(obj, dict):
                    return obj
            except Exception:
                pass
    return None


def one_try(model, extra):
    code, data = call("/chat/completions", {"model": model, "temperature": 0.2, "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": USER}], **extra})
    if code != 200:
        msg = data if isinstance(data, str) else str(data)
        m = re.search(r'"message"\s*:\s*"([^"]{0,110})', msg)
        return False, f"HTTP {code}: {(m.group(1) if m else msg[:110])}"
    msg = data["choices"][0]["message"]
    content = (msg.get("content") or "").strip()
    if not content:
        return False, "EMPTY reply" + (" (model tried a tool call)" if msg.get("tool_calls") else "")
    obj = parse(content)
    if obj and ("tool" in obj or "final" in obj):
        return True, "OK"
    return False, f"not valid agent JSON: {content[:60]!r}"


code, data = call("/models")
if code != 200:
    sys.exit(f"Could not list models: {data}")
models = [m["id"] for m in data["data"] if not any(x in m["id"] for x in ("whisper", "orpheus", "guard", "tts", "embed", "prompt"))]
print("Models found:", ", ".join(models), "\n")

winners = []
for model in models:
    variants = [("default", {})]
    if "gpt-oss" in model:
        variants.append(("reasoning_effort=low", {"reasoning_effort": "low"}))
    if "qwen" in model:
        variants.append(("reasoning_format=hidden", {"reasoning_format": "hidden"}))
    for vname, extra in variants:
        res = []
        for _ in range(2):
            ok, why = one_try(model, extra); res.append((ok, why)); time.sleep(1)
        good = all(ok for ok, _ in res)
        print(f"{'PASS' if good else 'FAIL'}  {model}  [{vname}]  ->  " + " | ".join(w for _, w in res))
        if good:
            winners.append((model, vname))

print()
if winners:
    plain = [m for m, v in winners if v == "default"]
    if plain:
        print("RECOMMENDED: put this in .env:\n  OPENAI_MODEL=" + plain[0])
        if len(plain) > 1:
            print("  OPENAI_FALLBACK_MODELS=" + ",".join(plain[1:]))
    else:
        print("Only works with an extra setting:", winners[0], "- send me this output and I will add it to the app.")
else:
    print("No model passed. If you see HTTP 429 above you hit a rate limit: wait a few minutes and run again. Send me this output.")