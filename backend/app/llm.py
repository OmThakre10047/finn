import hashlib
import json
import time

from . import db
from .config import GEMINI_API_KEY, LLM_CHEAP, LLM_STRONG

_client = None

RETRYABLE = ("429", "500", "503", "ResourceExhausted", "UNAVAILABLE", "Deadline")


def _get_client():
    global _client
    if _client is None:
        from google import genai

        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


def _cache_key(model: str, task: str, prompt: str) -> str:
    return hashlib.sha256(f"{model}|{task}|{prompt.strip()}".encode()).hexdigest()


def configured() -> bool:
    return bool(GEMINI_API_KEY and (LLM_CHEAP or LLM_STRONG))


def call(task: str, prompt: str, tier: str = "cheap", json_mode: bool = False, max_retries: int = 3) -> dict:
    """Returns {"text": str, "cached": bool, "model": str, "ok": bool, "error": str|None}."""
    model = LLM_STRONG if tier == "strong" else LLM_CHEAP
    if not model or not GEMINI_API_KEY:
        return {"text": "", "cached": False, "model": model or "unset", "ok": False, "error": "llm_not_configured"}

    key = _cache_key(model, task, prompt)
    with db.get_db() as conn:
        row = conn.execute("SELECT response_json FROM llm_cache WHERE key_hash = ?", (key,)).fetchone()
        if row:
            conn.execute("UPDATE llm_cache SET hits = hits + 1 WHERE key_hash = ?", (key,))
            conn.execute("INSERT INTO llm_calls (task, model, prompt_tokens, completion_tokens, cache_hit) VALUES (?, ?, 0, 0, 1)", (task, model))
            return {"text": json.loads(row["response_json"]), "cached": True, "model": model, "ok": True, "error": None}

    from google.genai import types

    err = None
    for attempt in range(max_retries):
        try:
            cfg = types.GenerateContentConfig(temperature=0.1)
            if json_mode:
                cfg.response_mime_type = "application/json"
            resp = _get_client().models.generate_content(model=model, contents=prompt, config=cfg)
            text = resp.text or ""
            usage = getattr(resp, "usage_metadata", None)
            pt = getattr(usage, "prompt_token_count", 0) or 0
            ct = getattr(usage, "candidates_token_count", 0) or 0
            with db.get_db() as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO llm_cache (key_hash, model, response_json) VALUES (?, ?, ?)",
                    (key, model, json.dumps(text)),
                )
                conn.execute(
                    "INSERT INTO llm_calls (task, model, prompt_tokens, completion_tokens, cache_hit) VALUES (?, ?, ?, ?, 0)",
                    (task, model, pt, ct),
                )
            return {"text": text, "cached": False, "model": model, "ok": True, "error": None}
        except Exception as e:
            err = f"{type(e).__name__}: {str(e)[:200]}"
            if not any(t in err for t in RETRYABLE):
                break
            time.sleep(2 * (attempt + 1))

    with db.get_db() as conn:
        conn.execute("INSERT INTO llm_calls (task, model, cache_hit) VALUES (?, ?, 0)", (task + ":error", model))
    return {"text": "", "cached": False, "model": model, "ok": False, "error": err}


def call_json(task: str, prompt: str, tier: str = "cheap"):
    """call() + JSON parse; returns parsed object or None."""
    r = call(task, prompt, tier=tier, json_mode=True)
    if not r["ok"]:
        return None
    try:
        return json.loads(r["text"])
    except json.JSONDecodeError:
        t = r["text"].strip()
        if t.startswith("```"):
            t = t.strip("`").lstrip("json").strip()
        try:
            return json.loads(t)
        except Exception:
            return None
