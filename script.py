cat > script.py << 'EOF'
#!/usr/bin/env python3
"""
LOOTLABS BOT v2.0 - Terminal Version
Automatically processes LootLabs links 5000 times with 1-minute intervals
Handles 1-click tasks and Cloudflare Turnstile verification automatically

Made by ISMOILOFF - Use at your own risk!
"""

import time
import re
import sys
import os
import asyncio
import json
import platform
import random
import subprocess
from typing import Optional
from urllib.parse import urlparse

# Selenium imports
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    from webdriver_manager.chrome import ChromeDriverManager
    from selenium.webdriver.chrome.service import Service
    import nodriver as uc
except ImportError:
    print("❌ Missing required packages. Install with:")
    print("pip install selenium webdriver-manager nodriver")
    sys.exit(1)

# ---------- CONFIG ----------
MAX_TASKS = 10         # Maximum number of tasks to attempt per cycle
TASK_TIMEOUT = 30      # Seconds to wait for a task to become clickable
TIMER_TIMEOUT = 120    # Max seconds to wait for a timer to finish
MAX_CYCLES = 5000      # Maximum number of times to repeat the process
CYCLE_DELAY = 60       # Seconds to wait between cycles (1 minute)
# ----------------------------

def get_lootlabs_url():
    """Get LootLabs URL from user input."""
    print("\n🤖 LOOTLABS BOT v2.0")
    print("=" * 50)
    print("🔥 This bot will automatically process a LootLabs link 5000 times!")
    print("⏱️  Each cycle takes ~1 minute")
    print("✅ Handles 1-click tasks + Cloudflare verification")
    print("=" * 50)

    while True:
        url = input("\n🔗 Enter LootLabs link: ").strip()
        if not url:
            continue
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        try:
            # Basic URL validation
            parsed = urlparse(url)
            if parsed.netloc and '.' in parsed.netloc:
                print(f"✅ Valid URL: {url}")
                return url
        except:
            pass
        print("❌ Invalid URL format. Please try again.")

def _find_chrome() -> str:
    """Return the Chrome executable path, checking common locations per OS."""
    if os.environ.get("CHROME_PATH"):
        return os.environ["CHROME_PATH"]

    if platform.system() == "Windows":
        candidates = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        ]
    else:
        candidates = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/usr/bin/google-chrome-stable",
            "/usr/bin/google-chrome",
            "/usr/bin/chromium-browser",
            "/usr/bin/chromium",
        ]

    for path in candidates:
        if os.path.isfile(path):
            return path

    raise FileNotFoundError(
        "Chrome not found in default locations. "
        "Set the CHROME_PATH environment variable to your Chrome executable."
    )

def _get_profile_dir() -> str:
    """Return a persistent Chrome profile directory for the current OS."""
    if os.environ.get("TS_PROFILE_DIR"):
        return os.environ["TS_PROFILE_DIR"]
    if platform.system() == "Windows":
        base = os.environ.get("TEMP") or os.environ.get("TMP") or r"C:\Temp"
        return os.path.join(base, "ts_profile")
    return "/tmp/ts_profile"

def _start_xvfb_if_needed() -> Optional[subprocess.Popen]:
    """On Linux headless servers, start a virtual display so Chrome can run."""
    if platform.system() != "Linux":
        return None
    if os.environ.get("DISPLAY"):
        return None
    proc = subprocess.Popen(
        ["Xvfb", ":99", "-screen", "0", "1280x900x24"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    os.environ["DISPLAY"] = ":99"
    time.sleep(0.5)
    return proc

async def solve_turnstile(sitekey: str, siteurl: str, timeout: int = 45) -> str:
    """Solve Cloudflare Turnstile captcha."""
    browser = await uc.start(
        browser_executable_path=_find_chrome(),
        headless=False,
        user_data_dir=_get_profile_dir(),
    )

    try:
        page = await browser.get(siteurl)
        await asyncio.sleep(random.uniform(2.0, 3.0))

        # Inject widget into the live page DOM
        await page.evaluate(f"""
            (() => {{
                if (document.getElementById('_ts_box')) return;
                window._tsToken = null;
                const wrap = document.createElement('div');
                wrap.id = '_ts_box';
                wrap.style = 'position:fixed;top:20px;left:20px;z-index:2147483647;';
                document.body.appendChild(wrap);
                window._tsLoad = function () {{
                    turnstile.render('#_ts_box', {{
                        sitekey: '{sitekey}',
                        callback: function(token) {{ window._tsToken = token; }}
                    }});
                }};
                const s = document.createElement('script');
                s.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?onload=_tsLoad&render=explicit';
                s.async = true;
                document.head.appendChild(s);
            }})();
        """)

        # Give Turnstile time to load and potentially auto-complete (invisible mode)
        await asyncio.sleep(5.0)

        async def get_token() -> Optional[str]:
            return await page.evaluate("""
                (() => {
                    if (window._tsToken) return window._tsToken;
                    const inp = document.querySelector('#_ts_box [name="cf-turnstile-response"]');
                    return (inp && inp.value) ? inp.value : null;
                })()
            """)

        async def get_cf_iframe_rect() -> Optional[dict]:
            raw = await page.evaluate("""
                JSON.stringify((() => {
                    for (const f of document.querySelectorAll('iframe')) {
                        const src = f.src || f.getAttribute('src') || '';
                        if (!src.includes('challenges.cloudflare.com')) continue;
                        const r = f.getBoundingClientRect();
                        if (r.width > 50 && r.height > 20) return {x:r.x, y:r.y, w:r.width, h:r.height};
                    }
                    return null;
                })())
            """)
            if raw and raw != 'null':
                return json.loads(raw)
            return None

        async def do_click(rect: Optional[dict]):
            if rect:
                cx = rect["x"] + 28 + random.uniform(-3, 3)
                cy = rect["y"] + rect["h"] / 2 + random.uniform(-3, 3)
                print(f"[captcha] clicking iframe at ({cx:.0f}, {cy:.0f})")
            else:
                # Widget is fixed at top:20px left:20px
                cx = 20 + 28 + random.uniform(-3, 3)
                cy = 20 + 32 + random.uniform(-3, 3)
                print(f"[captcha] clicking fixed position ({cx:.0f}, {cy:.0f})")
            await page.mouse_move(cx - 80, cy - 20)
            await asyncio.sleep(random.uniform(0.15, 0.25))
            await page.mouse_move(cx, cy)
            await asyncio.sleep(random.uniform(0.08, 0.15))
            await page.mouse_click(cx, cy)

        # Check if already auto-solved (invisible widget)
        token = await get_token()
        if token:
            return token

        # Wait up to 10s for the visible checkbox iframe to appear
        rect = None
        for _ in range(20):
            rect = await get_cf_iframe_rect()
            if rect:
                break
            await asyncio.sleep(0.5)

        # Click loop: click, wait, retry up to 3 times
        deadline = asyncio.get_event_loop().time() + timeout
        click_count = 0
        last_click = 0.0

        while asyncio.get_event_loop().time() < deadline:
            token = await get_token()
            if token:
                break

            now = asyncio.get_event_loop().time()
            if click_count == 0 or (not token and now - last_click > 8):
                if click_count >= 3:
                    await asyncio.sleep(0.3)
                    continue
                await do_click(rect)
                last_click = asyncio.get_event_loop().time()
                click_count += 1
                # After a click, refresh iframe rect in case it moved
                await asyncio.sleep(1.0)
                rect = await get_cf_iframe_rect() or rect
                continue

            await asyncio.sleep(0.3)

    finally:
        browser.stop()

    if not token:
        raise TimeoutError(f"Turnstile token not obtained within {timeout}s")

    return token

def handle_turnstile_captcha(driver):
    """Handle Cloudflare Turnstile captcha verification."""
    try:
        # Look for Turnstile captcha iframe
        captcha_iframe = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "iframe[src*='challenges.cloudflare.com']"))
        )

        # Extract sitekey from iframe src
        iframe_src = captcha_iframe.get_attribute("src")
        sitekey_match = re.search(r'sitekey=([^&]+)', iframe_src)

        if sitekey_match:
            sitekey = sitekey_match.group(1)
            current_url = driver.current_url

            print("🔐 Detected Turnstile captcha, solving...")

            try:
                # Solve captcha in separate browser
                token = asyncio.run(solve_turnstile(sitekey, current_url))

                # Inject token into the original page
                driver.execute_script(f"""
                    (() => {{
                        const input = document.querySelector('[name="cf-turnstile-response"]');
                        if (input) {{
                            input.value = '{token}';
                            // Trigger change event
                            input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        }}
                        // Also set it in the turnstile callback
                        if (window.turnstile) {{
                            window.turnstile._token = '{token}';
                        }}
                    }})();
                """)

                print("✅ Captcha solved successfully!")
                time.sleep(2)  # Wait for verification
                return True

            except Exception as e:
                print(f"❌ Failed to solve captcha: {e}")
                return False
        else:
            print("❌ Could not extract sitekey from captcha iframe")
            return False

    except TimeoutException:
        print("ℹ️  No captcha detected")
        return True
    except Exception as e:
        print(f"❌ Error handling captcha: {e}")
        return False

def setup_driver():
    """Set up Chrome with options that reduce bot detection."""
    options = webdriver.ChromeOptions()
    # options.add_argument("--headless")  # Uncomment for headless mode (may be detected)
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-plugins")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver

def wait_for_timer(driver, timeout=TIMER_TIMEOUT):
    """Wait until any timer on the page finishes."""
    print("⏳ Waiting for timer...")
    start = time.time()
    while time.time() - start < timeout:
        try:
            # Common timer patterns: "10s", "00:10", "10 seconds"
            timer_elem = driver.find_element(By.XPATH, "//*[contains(text(), 's') or contains(text(), ':') or contains(text(), 'second')]")
            text = timer_elem.text.strip()
            # If the text looks like a countdown and is not "0", keep waiting
            if re.search(r'\d', text):
                time.sleep(2)
                continue
        except NoSuchElementException:
            pass
        # No timer found – assume it's done
        break
    print("✅ Timer finished (or no timer found).")

def click_task(driver):
    """Find and click a task button/link. Returns True if a task was clicked."""
    # Common task selectors
    selectors = [
        (By.XPATH, "//button[contains(text(), 'Click')]"),
        (By.XPATH, "//a[contains(text(), 'Click')]"),
        (By.CSS_SELECTOR, "button.task-button"),
        (By.CSS_SELECTOR, "a.task-link"),
        (By.XPATH, "//button[contains(@class, 'task')]"),
        (By.XPATH, "//a[contains(@class, 'task')]"),
        (By.CSS_SELECTOR, "[data-task]"),
        # Generic clickable elements
        (By.CSS_SELECTOR, "button:not([disabled])"),
        (By.CSS_SELECTOR, "a[href]:not([href^='javascript:'])"),
    ]

    for by, sel in selectors:
        try:
            elem = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((by, sel))
            )
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", elem)
            time.sleep(1)
            elem.click()
            print(f"✅ Clicked task using selector: {sel}")
            return True
        except (TimeoutException, NoSuchElementException):
            continue
    return False

def close_extra_tabs(driver):
    """Close any new tabs/windows that opened after clicking a task."""
    if len(driver.window_handles) > 1:
        original = driver.window_handles[0]
        for handle in driver.window_handles[1:]:
            driver.switch_to.window(handle)
            driver.close()
        driver.switch_to.window(original)
        print("✅ Closed extra tab(s).")

def get_destination(driver):
    """After all tasks are done, try to find the final destination URL."""
    selectors = [
        (By.XPATH, "//a[contains(@href, 'http') and not(contains(@href, 'loot'))]"),
        (By.CSS_SELECTOR, "a.destination-link"),
        (By.CSS_SELECTOR, "a#final-link"),
        (By.CSS_SELECTOR, "a[href*='bit.ly'], a[href*='tinyurl'], a[href*='short']"),
    ]
    for by, sel in selectors:
        try:
            elem = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((by, sel))
            )
            href = elem.get_attribute("href")
            if href and "loot" not in href:
                return href
        except (TimeoutException, NoSuchElementException):
            continue
    return None

def process_single_cycle(driver, lootlabs_url, cycle_num):
    """Process one complete cycle of the LootLabs link."""
    print(f"\n{'='*50}")
    print(f"🚀 CYCLE {cycle_num}/{MAX_CYCLES} - {time.strftime('%H:%M:%S')}")
    print(f"{'='*50}")

    try:
        print(f"🌐 Opening: {lootlabs_url}")
        driver.get(lootlabs_url)
        time.sleep(5)  # Wait for page to load

        tasks_completed = 0

        for i in range(MAX_TASKS):
            print(f"\n--- Task {i+1} ---")

            # Wait for any timer before clicking
            wait_for_timer(driver)

            # Handle captcha if present
            if not handle_turnstile_captcha(driver):
                print(f"❌ Failed to handle captcha in task {i+1}")
                continue

            # Try to click a task
            if click_task(driver):
                tasks_completed += 1
                print(f"✅ Task {i+1} completed")

                # Wait for task to process
                time.sleep(3)
                close_extra_tabs(driver)
                time.sleep(2)
            else:
                print("⚠️  No more tasks found. Attempting to claim reward...")
                break

        # Try to get the final destination
        dest = get_destination(driver)
        if dest:
            print(f"🎉 Cycle {cycle_num} completed - Destination: {dest}")
            return True
        else:
            print(f"❌ Cycle {cycle_num} failed - Could not find destination URL")
            return False

    except Exception as e:
        print(f"❌ Error in cycle {cycle_num}: {e}")
        return False

def main():
    """Main bot function."""
    print("🤖 LOOTLABS BOT v2.0")
    print("=" * 50)

    # Get LootLabs URL from user
    lootlabs_url = get_lootlabs_url()

    # Setup Chrome driver
    driver = setup_driver()
    successful_cycles = 0
    failed_cycles = 0

    try:
        print(f"\n🎯 Starting bot with {MAX_CYCLES} cycles")
        print(f"📋 Target URL: {lootlabs_url}")
        print(f"⏱️  Delay between cycles: {CYCLE_DELAY} seconds")
        print("\n" + "="*60)

        for cycle in range(1, MAX_CYCLES + 1):
            success = process_single_cycle(driver, lootlabs_url, cycle)

            if success:
                successful_cycles += 1
            else:
                failed_cycles += 1

            # Show progress every 10 cycles
            if cycle % 10 == 0:
                print(f"\n📊 PROGRESS: {cycle}/{MAX_CYCLES} cycles completed")
                print(f"✅ Success: {successful_cycles} | ❌ Failed: {failed_cycles}")
                print(f"📈 Success rate: {(successful_cycles/cycle)*100:.1f}%")

            # Wait before next cycle (except on the last one)
            if cycle < MAX_CYCLES:
                print(f"⏳ Waiting {CYCLE_DELAY} seconds before next cycle...")
                time.sleep(CYCLE_DELAY)

        # Final summary
        print(f"\n{'='*60}")
        print("🎉 BOT COMPLETED!")
        print(f"📊 FINAL RESULTS:")
        print(f"✅ Successful cycles: {successful_cycles}")
        print(f"❌ Failed cycles: {failed_cycles}")
        print(f"📈 Success rate: {(successful_cycles/MAX_CYCLES)*100:.1f}%")
        print(f"⏱️  Total time: {time.strftime('%H:%M:%S', time.gmtime(MAX_CYCLES * (CYCLE_DELAY + 10)))}")
        print(f"{'='*60}")

        input("\nPress Enter to close the browser...")

    except KeyboardInterrupt:
        print(f"\n⏹️  Bot stopped by user after {cycle-1} cycles")
        print(f"✅ Successful: {successful_cycles} | ❌ Failed: {failed_cycles}")

    except Exception as e:
        print(f"\n💥 Critical error: {e}")

    finally:
        driver.quit()

if __name__ == "__main__":
    main()
EOF
