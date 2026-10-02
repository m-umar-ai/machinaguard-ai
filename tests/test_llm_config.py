"""Regression tests for the LLM request layer (no network, no real keys)."""
import json
import urllib.error
import utils.config as c


def _gemini_ok(text="hello"):
    return {"candidates": [{"content": {"parts": [{"text": text}]}}]}


def test_system_prompt_goes_to_system_slot_not_timeout(monkeypatch):
    """Bug fixed: callers pass (prompt, system) positionally; system used to land in the timeout slot and every live call crashed."""
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    seen = {}
    monkeypatch.setattr(c, "_post", lambda url, payload, headers, timeout: seen.update(payload=payload, timeout=timeout) or _gemini_ok("ok"))
    assert c.llm_text("question", "SYSTEM-TEXT") == "ok"
    assert isinstance(seen["timeout"], int) and "SYSTEM-TEXT" in json.dumps(seen["payload"])


def test_user_agent_header_is_sent(monkeypatch):
    seen = {}
    class R:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return b"{}"
    monkeypatch.setattr(c.urllib.request, "urlopen", lambda req, timeout=None: seen.update(h={k.lower(): v for k, v in req.header_items()}) or R())
    c._post("http://x", {}, {"Content-Type": "application/json"}, 5)
    assert seen["h"]["user-agent"].startswith("MachinaGuard")


def test_falls_back_to_second_provider(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "k"); monkeypatch.setenv("OPENAI_API_KEY", "k"); monkeypatch.setenv("LLM_PROVIDER", "openai")
    def post(url, payload, headers, timeout):
        if "chat/completions" in url: raise OSError("groq down")
        return _gemini_ok("from gemini")
    monkeypatch.setattr(c, "_post", post)
    assert c.llm_text("q", "s") == "from gemini" and c.LAST_LLM_ERROR is None


def test_empty_reply_is_retried_then_reported(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "k"); monkeypatch.setenv("OPENAI_FALLBACK_MODELS", "")
    calls = []
    monkeypatch.setattr(c, "_post", lambda *a: calls.append(1) or {"choices": [{"message": {"content": None}}]})
    assert c.llm_text("q") is None and len(calls) == 2 and "empty reply" in c.LAST_LLM_ERROR


def test_all_providers_failing_returns_none_with_reason(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.setattr(c, "_post", lambda *a: (_ for _ in ()).throw(OSError("down")))
    assert c.llm_text("q") is None and "gemini" in c.LAST_LLM_ERROR


def test_busy_groq_model_falls_back_to_second_model(monkeypatch):
    """A rate-limited model is skipped and the next model (own rate limit) answers."""
    monkeypatch.setenv("OPENAI_API_KEY", "k"); monkeypatch.setenv("OPENAI_MODEL", "big-model"); monkeypatch.setenv("OPENAI_FALLBACK_MODELS", "small-model")
    used = []
    def post(url, payload, headers, timeout):
        used.append(payload["model"])
        if payload["model"] == "big-model":
            raise urllib.error.HTTPError(url, 429, "rate limit", {}, None)
        return {"choices": [{"message": {"content": "answered by small"}}]}
    monkeypatch.setattr(c, "_post", post)
    assert c.llm_text("q") == "answered by small" and used[0] == "big-model" and used[-1] == "small-model"