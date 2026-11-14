#!/usr/bin/env python3
import sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.config import GEMINI_API_KEY

if not GEMINI_API_KEY:
    print("GEMINI_API_KEY not set"); sys.exit(1)

from google import genai
from google.genai import types

client = genai.Client(api_key=GEMINI_API_KEY)
CANDIDATES = [
    "gemini-3.5-flash-lite",
    "gemini-2.5-pro",
    "gemini-3.5-flash",
    "gemini-2.5-flash",
]
for m in CANDIDATES:
    t0 = time.time()
    try:
        r = client.models.generate_content(
            model=m, contents="reply OK",
            config=types.GenerateContentConfig(max_output_tokens=10, temperature=0),
        )
        txt = (r.text or "").strip()
        print(f"{m:28} OK   ({time.time()-t0:.1f}s) -> {txt[:20]!r}")
    except Exception as e:
        print(f"{m:28} FAIL ({time.time()-t0:.1f}s) {type(e).__name__}: {str(e)[:140]}")
