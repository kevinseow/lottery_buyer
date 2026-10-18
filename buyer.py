"""
Singapore Pools Automated TOTO Buyer Engine using Playwright.
Handles:
1. Login with Username & Password
2. Injecting 6-digit SMS OTP
3. Navigating to TOTO QuickPick section
4. Selecting bet type: QuickPick $1 (1 board), QuickPick $2 (2 boards), or System 7 $7 (1 board)
5. Adding to Bet Slip and placing the bet
6. Capturing screenshot of the confirmed purchase receipt
"""

import os
import re
import sys
import time
from typing import Dict, Optional, Tuple
from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

BASE_URL = "https://online.singaporepools.com"
TOTO_BET_URL = "https://online.singaporepools.com/lottery/toto/place-bet?source=ordinary&mode=self"


class SingaporePoolsBuyer:
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.is_logged_in = False

    def start_login(self, username: str, password: str) -> Tuple[bool, str]:
        """
        Launches browser, enters credentials, and submits login form.
        Waits until the 6-digit SMS OTP screen appears.
        """
        try:
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(
                headless=self.headless,
                slow_mo=300,
            )
            self.context = self.browser.new_context(
                viewport={"width": 1280, "height": 900},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
            )
            self.page = self.context.new_page()

            print("[BUYER] Navigating to Singapore Pools...")
            self.page.goto(BASE_URL, wait_until="networkidle")

            # Click Sign Up / Log In
            print("[BUYER] Opening login modal...")
            self.page.locator("text='Sign Up / Log In'").click()
            self.page.wait_for_selector("#input_login_username_field", timeout=10000)

            # Fill credentials
            print("[BUYER] Entering account credentials...")
            self.page.locator("#input_login_username_field").fill(username)
            self.page.locator("#input_login_password_field").fill(password)

            # Click Log In submit button
            print("[BUYER] Submitting credentials...")
            self.page.locator("button:has-text('Log In')").click()

            # Wait for either OTP input fields or error
            print("[BUYER] Waiting for SMS OTP screen (up to 45s)...")
            try:
                # CSS IDs starting with numbers must use attribute selector [id='...']
                self.page.wait_for_selector("[id='0_input_login_otp']", timeout=45000)
                self.page.screenshot(path="otp_screen.png")
                print("[BUYER] SMS OTP screen reached! Ready for 6-digit code.")
                return True, "SMS OTP dispatched to registered mobile."
            except Exception as wait_err:
                # Check if there is an error message on screen
                error_texts = []
                for selector in ["[role='alert']", ".error", ".toast", "text=/incorrect|invalid|exceeded|wait|locked/i"]:
                    matches = self.page.locator(selector).all()
                    for m in matches:
                        if m.is_visible():
                            txt = m.inner_text().strip()
                            if txt and txt not in error_texts:
                                error_texts.append(txt)

                if error_texts:
                    detail = " | ".join(error_texts)
                    return False, f"Singapore Pools message: {detail}"

                raise wait_err

        except Exception as e:
            err_msg = f"Failed during login initiation: {e}"
            print(f"[BUYER ERROR] {err_msg}", file=sys.stderr)
            if self.page:
                self.page.screenshot(path="login_error.png")
            self.close()
            return False, err_msg

    def submit_otp(self, otp_code: str) -> Tuple[bool, str]:
        """
        Inputs the 6-digit OTP received from Telegram and submits it.
        """
        if not self.page:
            return False, "Browser session not active."

        otp_code = otp_code.strip()
        if len(otp_code) != 6 or not otp_code.isdigit():
            return False, "OTP must be exactly 6 digits."

        try:
            print(f"[BUYER] Injecting OTP digits: {otp_code}")
            for idx, digit in enumerate(otp_code):
                box_selector = f"[id='{idx}_input_login_otp']"
                self.page.locator(box_selector).fill(digit)
                self.page.wait_for_timeout(100)

            # Click Submit button
            print("[BUYER] Submitting OTP verification...")
            self.page.locator("button:has-text('Submit')").click()

            # Wait for login completion (modal dismisses, or 'My Bets' is active, or URL changes)
            self.page.wait_for_timeout(4000)
            self.page.screenshot(path="after_otp_submit.png")

            # Check if OTP error message is displayed
            error_locator = self.page.locator("text=/invalid.*code|incorrect.*otp/i")
            if error_locator.count() > 0 and error_locator.first.is_visible():
                return False, "Invalid OTP code entered."

            self.is_logged_in = True
            print("[BUYER] Successfully logged into Singapore Pools!")
            return True, "Login verified successfully."

        except Exception as e:
            err_msg = f"Failed submitting OTP: {e}"
            print(f"[BUYER ERROR] {err_msg}", file=sys.stderr)
            return False, err_msg

    def place_bet(self, bet_code: str = "QP1") -> Dict:
        """
        Places the specified TOTO bet:
        - QP1: QuickPick Ordinary 1 Board ($1)
        - QP2: QuickPick Ordinary 2 Boards ($2)
        - SYS7: QuickPick System 7 1 Board ($7)
        """
        if not self.is_logged_in or not self.page:
            return {"success": False, "error": "Not logged in to Singapore Pools."}

        try:
            print(f"[BUYER] Navigating to TOTO betting page: {TOTO_BET_URL}")
            self.page.goto(TOTO_BET_URL, wait_until="networkidle")

            # Click the Quick Pick tab
            print("[BUYER] Selecting Quick Pick tab...")
            self.page.locator("text='Quick Pick'").first.click()
            self.page.wait_for_timeout(1500)

            # Determine bet target
            if bet_code in ("QP1", "QP2"):
                count = "1" if bet_code == "QP1" else "2"
                print(f"[BUYER] Configuring Ordinary QuickPick: {count} board(s)...")
                card = self.page.locator("div").filter(has_text="Ordinary").filter(has_text="$1.00").last
                card.locator("input").fill(count)

            elif bet_code == "SYS7":
                print("[BUYER] Configuring System 7 QuickPick: 1 board ($7.00)...")
                card = self.page.locator("div").filter(has_text="System 7").filter(has_text="$7.00").last
                card.locator("input").fill("1")

            self.page.wait_for_timeout(1000)
            self.page.screenshot(path="before_add_to_slip.png")

            # Click 'Add to Bet Slip'
            print("[BUYER] Adding selection to bet slip...")
            self.page.locator("button:has-text('Add to Bet Slip')").click()
            self.page.wait_for_timeout(2000)

            self.page.screenshot(path="bet_slip_ready.png")

            # Look for Place Bet / Confirm Bet button on the right-side Bet Slip
            print("[BUYER] Submitting final bet order...")
            place_bet_btn = self.page.locator("button:has-text('Place Bet'), button:has-text('Confirm Bet'), button:has-text('Submit Bet')").first
            if place_bet_btn.is_visible():
                place_bet_btn.click()
                self.page.wait_for_timeout(4000)

            # Capture confirmed receipt screenshot
            receipt_path = os.path.abspath("toto_purchase_receipt.png")
            self.page.screenshot(path=receipt_path)
            print(f"[BUYER] Bet placed! Receipt saved to {receipt_path}")

            return {
                "success": True,
                "bet_code": bet_code,
                "receipt_path": receipt_path,
                "message": f"Successfully purchased {bet_code}!",
            }

        except Exception as e:
            err_msg = f"Failed placing TOTO bet: {e}"
            print(f"[BUYER ERROR] {err_msg}", file=sys.stderr)
            if self.page:
                self.page.screenshot(path="bet_error.png")
            return {"success": False, "error": err_msg}

        finally:
            self.close()

    def close(self):
        """Closes browser and cleans up."""
        try:
            if self.context:
                self.context.close()
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
        except:
            pass
        self.context = None
        self.browser = None
        self.playwright = None
        self.page = None
        self.is_logged_in = False
        print("[BUYER] Browser session closed.")
