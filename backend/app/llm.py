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


def _cache_key(model: str, task: str, prompt: str, images: list[bytes] | None = None) -> str:
    h = hashlib.sha256(f"{model}|{task}|{prompt.strip()}".encode())
    for img in images or []:
        h.update(b"|img|")
        h.update(hashlib.sha256(img).digest())
    return h.hexdigest()


def configured() -> bool:
    return bool(GEMINI_API_KEY and (LLM_CHEAP or LLM_STRONG))


def call(task: str, prompt: str, tier: str = "cheap", json_mode: bool = False, max_retries: int = 3, images: list[bytes] | None = None) -> dict:
    """Returns {"text": str, "cached": bool, "model": str, "ok": bool, "error": str|None}."""
    model = LLM_STRONG if tier == "strong" else LLM_CHEAP
    if not model or not GEMINI_API_KEY:
        return {"text": "", "cached": False, "model": model or "unset", "ok": False, "error": "llm_not_configured"}

    key = _cache_key(model, task, prompt, images)
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
            cfg_kwargs = {"temperature": 0.1}
            if tier == "strong":
                cfg_kwargs["max_output_tokens"] = 24576
                cfg_kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=1024)
            if json_mode:
                cfg_kwargs["response_mime_type"] = "application/json"
            cfg = types.GenerateContentConfig(**cfg_kwargs)
            contents: list = [prompt]
            for img in images or []:
                contents.append(types.Part.from_bytes(data=img, mime_type="image/png"))
            resp = _get_client().models.generate_content(model=model, contents=contents, config=cfg)
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


def call_json(task: str, prompt: str, tier: str = "cheap", images: list[bytes] | None = None):
    """call() + JSON parse; returns parsed object or None."""
    r = call(task, prompt, tier=tier, json_mode=True, images=images)
    if not r["ok"]:
        return None
    return _parse_json_loose(r["text"])


def _parse_json_loose(text: str):
    """json.loads, then fence-stripped loads, then raw_decode (ignores trailing junk)."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`").lstrip("json").strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        pass
    dec = json.JSONDecoder()
    try:
        obj, _ = dec.raw_decode(t.lstrip())
        return obj
    except json.JSONDecodeError:
        return None


def call_json_strict(task: str, prompt: str, tier: str = "cheap", max_retries: int = 2):
    """Returns (data, error). error is None on success; on failure it names what broke
    (HTTP error vs unparseable JSON, with a raw-response excerpt)."""
    last_err = None
    for _ in range(max_retries):
        r = call(task, prompt, tier=tier, json_mode=True)
        if not r["ok"]:
            last_err = f"llm call failed: {r['error']}"
            continue
        data = _parse_json_loose(r["text"])
        if data is not None:
            return data, None
        last_err = (
            f"unparseable JSON (textlen={len(r['text'])}, "
            f"head={r['text'][:120]!r}, tail={r['text'][-120:]!r})"
        )
    return None, last_err
