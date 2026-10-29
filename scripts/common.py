"""Shared helpers: API key loading (never printed), paths, timestamps."""
import csv
import datetime as dt
import os
import sys
from pathlib import Path

from dotenv import dotenv_values, load_dotenv

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RESULTS = ROOT / "results"
AUDIO_16K = RESULTS / "audio_16k"

BASE_URL = "https://api.vachana.ai"
WS_STT_URL = "wss://api.vachana.ai/stt/v3/stream"


def api_key() -> str:
    load_dotenv(ROOT / ".env")
    key = (os.getenv("GNANI_API_KEY") or "").strip()
    placeholder = (dotenv_values(ROOT / ".env.example").get("GNANI_API_KEY") or "").strip()
    if not key or key == placeholder:
        sys.exit("GNANI_API_KEY missing or still the .env.example placeholder. Paste your key into .env.")
    return key


def stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def load_clips(only=None):
    """Clips from clip_scripts.csv that have a converted 16 kHz WAV, optionally filtered by id."""
    with open(DATA / "clip_scripts.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    clips = [r for r in rows if (AUDIO_16K / f"{r['clip_id']}.wav").exists()]
    if only:
        wanted = [c.strip() for c in only.split(",")]
        clips = [r for r in clips if r["clip_id"] in wanted]
    return clips


def pick_headers(headers) -> dict:
    """All response headers except anything that could echo credentials."""
    return {k: v for k, v in headers.items() if "key" not in k.lower() and "auth" not in k.lower()
            and "cookie" not in k.lower()}


# ---------- Sarvam (Day 3 reference only) ----------
SARVAM_BASE_URL = "https://api.sarvam.ai"
SARVAM_WS_STT_URL = "wss://api.sarvam.ai/speech-to-text-realtime/ws"


def sarvam_key() -> str:
    load_dotenv(ROOT / ".env")
    key = (os.getenv("SARVAM_API_KEY") or "").strip()
    if not key:
        sys.exit("SARVAM_API_KEY missing from .env.")
    return key
