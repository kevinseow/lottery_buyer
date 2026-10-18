"""
Purchase History & Idempotency Tracker for TOTO Buyer.
Prevents duplicate purchases and duplicate alerts for the same draw.
"""

from datetime import datetime
import json
import os
from typing import Dict, List, Optional

HISTORY_FILE = os.path.join(os.path.dirname(__file__), "purchases.json")


def load_history() -> List[Dict]:
    """Loads recorded purchases from local JSON file."""
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_history(records: List[Dict]):
    """Saves records to local JSON file."""
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)


def has_purchased_for_draw(draw_date: str) -> bool:
    """Returns True if a purchase has already been completed for the specified draw date."""
    records = load_history()
    clean_draw = draw_date.strip().lower()
    return any(r.get("draw_date", "").strip().lower() == clean_draw for r in records)


def record_purchase(
    draw_date: str, bet_code: str, bet_name: str, cost: int, receipt_path: Optional[str] = None
) -> Dict:
    """Records a completed purchase."""
    records = load_history()
    entry = {
        "timestamp": datetime.now().isoformat(),
        "draw_date": draw_date,
        "bet_code": bet_code,
        "bet_name": bet_name,
        "cost": cost,
        "receipt_path": receipt_path,
    }
    records.append(entry)
    save_history(records)
    return entry


def get_latest_purchase() -> Optional[Dict]:
    """Returns the most recent purchase record."""
    records = load_history()
    if records:
        return records[-1]
    return None
