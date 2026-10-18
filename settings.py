"""
Persistent Settings Manager for TOTO Auto-Buyer.
Allows dynamic adjustment of threshold and schedule without restarting.
"""

import json
import os
import re
from typing import Optional

SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "settings.json")
DEFAULT_THRESHOLD = 2_000_000


def load_settings() -> dict:
    """Loads configuration from settings.json or returns defaults."""
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    # Default fallback: check environment variable or use 2M
    env_threshold = os.getenv("JACKPOT_THRESHOLD")
    threshold = int(env_threshold) if env_threshold and env_threshold.isdigit() else DEFAULT_THRESHOLD
    return {"jackpot_threshold": threshold}


def save_settings(settings: dict):
    """Saves settings dict to settings.json."""
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)


def get_threshold() -> int:
    """Returns the current jackpot threshold."""
    return load_settings().get("jackpot_threshold", DEFAULT_THRESHOLD)


def set_threshold(amount: int):
    """Updates the jackpot threshold and persists it."""
    settings = load_settings()
    settings["jackpot_threshold"] = int(amount)
    save_settings(settings)


def parse_amount_str(raw: str) -> Optional[int]:
    """
    Parses human inputs like:
    '3m' -> 3000000
    '2.5m' -> 2500000
    '$5,000,000' -> 5000000
    '4000000' -> 4000000
    """
    text = raw.strip().lower().replace("$", "").replace(",", "")

    # Handle million shorthand: 2.5m, 3m, 5 million
    m_match = re.match(r"^([0-9]+(?:\.[0-9]+)?)\s*(?:m|million)?$", text)
    if not m_match:
        return None

    val = float(m_match.group(1))
    if "m" in text or "million" in text or val < 100:
        # User entered e.g. '3', '3m', '2.5'
        return int(val * 1_000_000)
    else:
        # User entered full number e.g. '3000000'
        return int(val)
