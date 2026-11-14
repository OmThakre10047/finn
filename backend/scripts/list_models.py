#!/usr/bin/env python3
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import GEMINI_API_KEY

if not GEMINI_API_KEY:
    print("GEMINI_API_KEY not set — fill backend/.env first (names only are in .env.example).")
    sys.exit(1)

from google import genai

client = genai.Client(api_key=GEMINI_API_KEY)
print(f"{'MODEL ID':50} {'IN':>10} {'OUT':>10}  ACTIONS")
for m in client.models.list():
    actions = m.supported_actions or []
    if "generateContent" in actions:
        print(f"{m.name:50} {str(m.input_token_limit):>10} {str(m.output_token_limit):>10}  {','.join(actions)}")
