"""Print the Gemini models your API key can use.

Usage:  python list_models.py
"""
import os
import sys
from pathlib import Path

try:
    from google import genai
except ImportError:
    sys.exit("Missing library. Run:  pip install google-genai")

env = Path(".env")
if env.exists():
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

if not os.environ.get("GEMINI_API_KEY"):
    sys.exit("No API key found in .env")

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
print("Models you can use for answering:\n")
for m in client.models.list():
    if "generateContent" in (getattr(m, "supported_actions", None) or []):
        print("  " + m.name.replace("models/", ""))