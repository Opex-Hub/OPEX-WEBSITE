import time
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service

# ---------- CONFIG ----------
LOOTLABS_URL = "https://loot-link.com/s?XXXXXXXX"  # Replace with your actual LootLabs link
MAX_TASKS = 5          # Maximum number of tasks to attempt
TASK_TIMEOUT = 30      # Seconds to wait for a task to become clickable
TIMER_TIMEOUT = 120    # Max seconds to wait for a timer to finish
# ----------------------------

def setup_driver():
    """Set up Chrome with options that reduce bot detection."""
    options = webdriver.ChromeOptions()
    # options.add_argument("--headless")  # Uncomment for headless mode (may be detected)
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver

def wait_for_timer(driver, timeout=TIMER_TIMEOUT):
    """
    Wait until any timer on the page finishes.
    This looks for a countdown element (e.g., a <span> with numbers and 's').
    Adjust the selector to match the actual timer element.
    """
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
    """
    Find and click a task button/link.
    Returns True if a task was clicked, False otherwise.
    """
    # Common task selectors – update these after inspecting the page.
    selectors = [
        (By.XPATH, "//button[contains(text(), 'Click')]"),
        (By.XPATH, "//a[contains(text(), 'Click')]"),
        (By.CSS_SELECTOR, "button.task-button"),
        (By.CSS_SELECTOR, "a.task-link"),
        (By.XPATH, "//button[contains(@class, 'task')]"),
        (By.XPATH, "//a[contains(@class, 'task')]"),
        (By.CSS_SELECTOR, "[data-task]"),
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
    """
    After all tasks are done, the final link should be revealed.
    Try to find it and return the URL.
    """
    # Look for a link that is now visible/clickable
    selectors = [
        (By.XPATH, "//a[contains(@href, 'http') and not(contains(@href, 'loot'))]"),
        (By.CSS_SELECTOR, "a.destination-link"),
        (By.CSS_SELECTOR, "a#final-link"),
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

def main():
    driver = setup_driver()
    try:
        print(f"🌐 Opening: {LOOTLABS_URL}")
        driver.get(LOOTLABS_URL)
        time.sleep(3)  # Initial load

        for i in range(MAX_TASKS):
            print(f"\n--- Task {i+1} ---")
            # Wait for any timer before clicking
            wait_for_timer(driver)

            # Try to click a task
            if not click_task(driver):
                print("⚠️  No more tasks found. Attempting to claim reward...")
                break

            # Wait a moment for the task to process
            time.sleep(2)
            close_extra_tabs(driver)

            # Small delay before next iteration
            time.sleep(3)

        # Try to get the final destination
        dest = get_destination(driver)
        if dest:
            print(f"\n🎉 Destination URL: {dest}")
        else:
            print("\n❌ Could not find destination URL. You may need to manually check the page.")
            input("Press Enter to close the browser...")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
