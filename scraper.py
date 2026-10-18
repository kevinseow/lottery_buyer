"""
TOTO Prize Quantum Scraper for Singapore Pools.
Fetches the latest estimated jackpot and next draw schedule.
"""

from dataclasses import dataclass
import re
import sys
import urllib.request
from typing import Optional

# Ensure UTF-8 output on Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

TOTO_ESTIMATE_URL = (
    "https://www.singaporepools.com.sg/DataFileArchive/Lottery/Output/toto_next_draw_estimate_en.html"
)
TOTO_RESULTS_URL = (
    "https://www.singaporepools.com.sg/en/product/sr/Pages/toto_results.aspx"
)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


@dataclass
class TotoJackpotInfo:
    amount: int  # Numerical value, e.g. 2500000
    formatted_amount: str  # e.g. "$2,500,000 est"
    draw_date: str  # e.g. "Mon, 19 Oct 2026, 6.30pm"
    source_url: str

    def meets_threshold(self, threshold: int = 2_000_000) -> bool:
        """Returns True if the estimated jackpot meets or exceeds the threshold."""
        return self.amount >= threshold


def fetch_html(url: str, timeout: int = 10) -> str:
    """Fetches HTML string from the given URL with standard browser headers."""
    req = urllib.request.Request(url, headers=DEFAULT_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="ignore")


def parse_next_draw_estimate(html: str, source_url: str) -> Optional[TotoJackpotInfo]:
    """Parses the pregenerated HTML snippet containing jackpot and draw date."""
    # Pattern 1: $X,XXX,XXX est
    jackpot_match = re.search(r"\$([0-9,]+)(?:\s*est)?", html, re.IGNORECASE)
    # Pattern 2: class='toto-draw-date'>...</div>
    date_match = re.search(
        r"class=['\"]toto-draw-date['\"][^>]*>([^<]+)</div>", html, re.IGNORECASE
    )

    if not jackpot_match:
        return None

    raw_amount_str = jackpot_match.group(1).replace(",", "")
    amount = int(raw_amount_str)
    formatted_amount = f"${amount:,} est"

    draw_date = "Unknown"
    if date_match:
        # Clean up whitespace and extra commas
        raw_date = date_match.group(1).strip()
        draw_date = re.sub(r"\s+", " ", raw_date)

    return TotoJackpotInfo(
        amount=amount,
        formatted_amount=formatted_amount,
        draw_date=draw_date,
        source_url=source_url,
    )


def get_current_toto_jackpot(timeout: int = 10) -> TotoJackpotInfo:
    """
    Primary entrypoint. Attempts to fetch from the fast static snippet first.
    Falls back to the main results page if the snippet is unavailable.
    """
    # Attempt 1: Fast dedicated estimate file
    try:
        html = fetch_html(TOTO_ESTIMATE_URL, timeout=timeout)
        info = parse_next_draw_estimate(html, TOTO_ESTIMATE_URL)
        if info:
            return info
    except Exception as e:
        print(f"[WARN] Failed fetching from static estimate URL: {e}", file=sys.stderr)

    # Attempt 2: Fallback to the main results page
    try:
        html = fetch_html(TOTO_RESULTS_URL, timeout=timeout)
        info = parse_next_draw_estimate(html, TOTO_RESULTS_URL)
        if info:
            return info
    except Exception as e:
        print(f"[ERROR] Failed fetching from main results URL: {e}", file=sys.stderr)

    raise RuntimeError("Could not retrieve current TOTO jackpot info from Singapore Pools.")


if __name__ == "__main__":
    print("Checking Singapore Pools for latest TOTO prize quantum...")
    try:
        info = get_current_toto_jackpot()
        print("\n" + "=" * 45)
        print("🎰 SINGAPORE POOLS TOTO JACKPOT REPORT")
        print("=" * 45)
        print(f"💰 Estimated Jackpot : {info.formatted_amount} (${info.amount:,})")
        print(f"📅 Next Draw Date    : {info.draw_date}")
        print(f"🎯 Target Threshold  : $2,000,000")
        meets = info.meets_threshold(2_000_000)
        print(f"🚨 Exceeds $2M Target: {'YES! ALERT TRIGGERED' if meets else 'NO (Wait for snowball)'}")
        print("=" * 45)
    except Exception as err:
        print(f"❌ Error checking jackpot: {err}")
        sys.exit(1)
