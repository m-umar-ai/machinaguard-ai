"""Central config + optional LLM access. Never hard-code keys: use .env.

Providers (first key found wins; override with LLM_PROVIDER=gemini|openai):
  GEMINI_API_KEY   -> Google Gemini REST            (model: GEMINI_MODEL, default gemini-3.8-flash)
  OPENAI_API_KEY   -> any OpenAI-compatible endpoint (OPENAI_BASE_URL, OPENAI_MODEL, optional OPENAI_FALLBACK_MODELS) e.g. Groq / OpenRouter
Every call returns None on ANY failure so callers fall back to offline logic.
"""
import json, os, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODEL_PATH = ROOT / "models" / "anomaly_model.joblib"
DOCS_DIR = ROOT / "data" / "maintenance_docs"
SENSOR_CSV = ROOT / "data" / "sensor_data.csv"

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:
    pass

SENSORS = ["temperature", "vibration", "pressure", "rpm", "energy", "production_rate"]
UNITS = {"temperature": "°C", "vibration": "mm/s", "pressure": "bar", "rpm": "rpm",
         "energy": "kW", "production_rate": "units/h", "vibration_b": "mm/s", "vib_disagreement": "mm/s"}

# Clearly SIMULATED business assumptions (not real factory figures)
ASSUMPTIONS = {"margin_per_unit_usd": 12.0, "repair_cost_usd": 3500.0,
               "unplanned_downtime_multiplier": 3.0, "planned_inspection_hours": 2.5}

_OVERRIDE = None  # tests / demos can inject a fake LLM: fn(prompt, system=None) -> str | None


def set_llm_override(fn):
    global _OVERRIDE
    _OVERRIDE = fn


def llm_provider():
    if _OVERRIDE is not None:
        return "override"
    pref = os.getenv("LLM_PROVIDER", "").lower()
    if pref == "openai" and os.getenv("OPENAI_API_KEY"):
        return "openai"
    if os.getenv("GEMINI_API_KEY") and pref in ("", "gemini"):
        return "gemini"
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    return None


def llm_available() -> bool:
    return llm_provider() is not None


def llm_name() -> str:
    p = llm_provider()
    return {"gemini": os.getenv("GEMINI_MODEL", "gemini-3.8-flash"),
            "openai": os.getenv("OPENAI_MODEL", "openai/gpt-oss-120b"),
            "override": "test-llm"}.get(p, "offline")


def _post(url, payload, headers, timeout):
    # A browser-like User-Agent is required: Groq's Cloudflare blocks Python's default one (error 1010).
    headers = {"User-Agent": "MachinaGuard/1.0", **headers}
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


LAST_LLM_ERROR = None  # why the last LLM call fell back to offline logic (shown in the UI)
_COOLDOWN = {}         # (provider, model) -> time until which a rate-limited model is skipped


def _post_retry(url, payload, headers, timeout):
    """One retry when the provider says it is busy (HTTP 503). Rate limits (429) are not retried: they do not clear in 2 seconds."""
    import time, urllib.error
    for attempt in range(2):
        try:
            return _post(url, payload, headers, timeout)
        except urllib.error.HTTPError as e:
            if e.code == 503 and attempt == 0:
                time.sleep(2)
                continue
            raise


def _openai_models():
    """Primary model first, then fallbacks. Each Groq model has its OWN rate limit, so a busy model can be skipped automatically."""
    base = os.getenv("OPENAI_BASE_URL", "https://api.groq.com/openai/v1")
    primary = os.getenv("OPENAI_MODEL", "openai/gpt-oss-120b")
    default_fb = "openai/gpt-oss-20b" if "groq" in base else ""
    extra = [m.strip() for m in os.getenv("OPENAI_FALLBACK_MODELS", default_fb).split(",") if m.strip()]
    out = []
    for m in [primary] + extra:
        if m not in out:
            out.append(m)
    return out


def _call(provider, prompt, system, timeout, model=None):
    """One provider + one model, one request. Raises on any failure. Empty replies count as failures (reasoning models sometimes return nothing)."""
    if provider == "gemini":
        key, model = os.getenv("GEMINI_API_KEY"), model or os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        body = {"contents": [{"parts": [{"text": prompt}]}]}
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        data = _post_retry(url, body, {"Content-Type": "application/json", "x-goog-api-key": key}, timeout)
        out = data["candidates"][0]["content"]["parts"][0]["text"]
    else:
        base = os.getenv("OPENAI_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
        msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
        data = _post_retry(f"{base}/chat/completions", {"model": model or _openai_models()[0], "messages": msgs, "temperature": 0.2},
                           {"Content-Type": "application/json", "Authorization": "Bearer " + os.getenv("OPENAI_API_KEY", "")}, timeout)
        out = data["choices"][0]["message"]["content"]
    out = (out or "").strip()
    if not out:
        raise ValueError("empty reply from model")
    return out


def llm_text(prompt: str, system: str | None = None, timeout: int | None = None):
    """Return LLM text, or None on ANY failure (callers then use their offline logic).
    NOTE: argument order is (prompt, system, timeout) - callers pass the system prompt as the 2nd positional argument.
    Order tried: preferred provider (all its models), then the other provider if its key exists.
    Example: Groq 120b rate-limited -> Groq 20b -> Gemini -> offline. The reason for a fallback is kept in LAST_LLM_ERROR."""
    global LAST_LLM_ERROR
    timeout = timeout or int(os.getenv("LLM_TIMEOUT", "40"))
    first = llm_provider()
    if first is None:
        return None
    if first == "override":
        try:
            return _OVERRIDE(prompt, system)
        except Exception as e:
            LAST_LLM_ERROR = f"{type(e).__name__}: {str(e)[:160]}"
            return None
    order = [first] + [p for p in ("gemini", "openai") if p != first and os.getenv("GEMINI_API_KEY" if p == "gemini" else "OPENAI_API_KEY")]
    errors = []
    import time
    for prov in order:
        models = _openai_models() if prov == "openai" else [None]
        models = [m for m in models if _COOLDOWN.get((prov, m), 0) <= time.time()] or models  # skip models that were just rate-limited
        for model in models:
            for attempt in range(2):  # 2nd attempt only matters for empty replies
                try:
                    out = _call(prov, prompt, system, timeout, model)
                    LAST_LLM_ERROR = None
                    return out
                except Exception as e:
                    detail = e.read().decode()[:90] if hasattr(e, "read") else str(e)[:90]
                    if getattr(e, "code", None) == 429:
                        _COOLDOWN[(prov, model)] = time.time() + 60
                    msg = f"{model or prov}: {type(e).__name__} {detail}".replace("\n", " ")
                    if not isinstance(e, ValueError) or attempt == 1:
                        errors.append(msg)
                        break
    LAST_LLM_ERROR = " | ".join(errors)
    return None