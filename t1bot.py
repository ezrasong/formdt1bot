import time
import random
import os
import sys
import atexit
import winsound
from curl_cffi import requests as crequests
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

# Always resolve paths relative to this file so .env is used no matter where we run from.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.environ.get("ENV_PATH") or os.path.join(BASE_DIR, ".env")
SESSION_DIR = os.path.join(BASE_DIR, "ghost_session_data")
LOGIN_URL = "https://formdt1.com/account/login"
BROWSER_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
VIEWPORT = {"width": 1280, "height": 900}
ACCEPT_LANGUAGE = "en-US,en;q=0.9"
TIMEZONE_ID = "America/New_York"
HARDWARE_CONCURRENCY = 8
DEVICE_MEMORY_GB = 8
DOWNLINK_MBPS = 10
RTT_MS = 50
INITIAL_BACKOFF_SECONDS = 2
MAX_BACKOFF_SECONDS = 60
LAUNCH_ARGS = [
    "--start-maximized",
    "--disable-blink-features=AutomationControlled",
    "--disable-features=IsolateOrigins,site-per-process,SitePerProcess",
    "--disable-infobars",
]

stealth_engine = Stealth()

def load_env(path=ENV_PATH):
    if not os.path.exists(path):
        return
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ[key.strip()] = value.strip()

load_env()

def require_env(key, friendly_name=None):
    val = os.getenv(key)
    if val is None or val.strip() == "":
        label = friendly_name or key
        raise RuntimeError(f"Missing required environment variable: {label} ({key})")
    return val.strip()

HTTP_SESSION = crequests.Session()
HTTP_SESSION.headers.update(
    {
        "Accept": "application/json,text/plain;q=0.9,*/*;q=0.8",
        "Accept-Language": ACCEPT_LANGUAGE,
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Referer": "https://formdt1.com/",
    }
)
atexit.register(HTTP_SESSION.close)

def http_get(url, **kwargs):
    """Reuse a single session to reduce per-request memory/CPU."""
    return HTTP_SESSION.get(url, impersonate="chrome120", **kwargs)

CALL_LINKS = {
    "Titanium": require_env("CALL_LINK_TITANIUM", "Titanium call link"),
    "Silver": require_env("CALL_LINK_SILVER", "Silver call link"),
}

VARIANTS = {
    require_env("VARIANT_TITANIUM_ID", "Titanium variant id"): {
        "name": require_env("VARIANT_TITANIUM_NAME", "Titanium name"),
        "url": require_env("VARIANT_TITANIUM_URL", "Titanium product url"),
    },
    require_env("VARIANT_SILVER_ID", "Silver variant id"): {
        "name": require_env("VARIANT_SILVER_NAME", "Silver name"),
        "url": require_env("VARIANT_SILVER_URL", "Silver product url"),
    },
}
BACKOFF = {v_id: {"cooldown_until": 0.0, "current": 0.0} for v_id in VARIANTS}

def launch_profile(p, headless=False):
    """Create a persistent profile with the same UA everywhere."""
    context = p.chromium.launch_persistent_context(
        SESSION_DIR,
        headless=headless,
        channel="chrome",
        viewport=VIEWPORT,
        user_agent=BROWSER_USER_AGENT,
        args=LAUNCH_ARGS,
        locale="en-US",
        timezone_id=TIMEZONE_ID,
        color_scheme="light",
        ignore_default_args=["--enable-automation"],
    )
    context.set_extra_http_headers({"Accept-Language": ACCEPT_LANGUAGE})
    apply_context_stealth(context)
    return context

def new_stealth_page(context):
    page = context.new_page()
    stealth_engine.apply_stealth_sync(page)
    page.bring_to_front()
    return page

def apply_context_stealth(context):
    """Hide common automation flags that trigger blank/blocked pages."""
    context.add_init_script(
        """
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        window.chrome = window.chrome || { runtime: {} };
        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
        Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
        Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => %(hw)d });
        Object.defineProperty(navigator, 'deviceMemory', { get: () => %(dm)d });
        Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
        Object.defineProperty(navigator, 'maxTouchPoints', { get: () => 0 });
        Object.defineProperty(navigator, 'connection', { get: () => ({
            downlink: %(dl)f,
            effectiveType: '4g',
            rtt: %(rtt)d,
            saveData: false
        })});
        const getParameter = WebGLRenderingContext.prototype.getParameter;
        WebGLRenderingContext.prototype.getParameter = function(parameter) {
            if (parameter === 37445) return "Intel Open Source Technology Center";
            if (parameter === 37446) return "Mesa DRI Intel(R) UHD Graphics 620 (KBL GT2)";
            return getParameter.call(this, parameter);
        };
        """
        % {"hw": HARDWARE_CONCURRENCY, "dm": DEVICE_MEMORY_GB, "dl": float(DOWNLINK_MBPS), "rtt": RTT_MS}
    )

def load_login(page):
    """Ensure the FormD login form actually renders before we wait."""
    page.goto(LOGIN_URL, wait_until="networkidle")
    try:
        page.wait_for_selector("form#customer_login", timeout=20000)
    except Exception:
        print("[!] Login page looked empty. Reloading once...")
        page.reload(wait_until="networkidle")
        page.wait_for_selector("form#customer_login", timeout=20000)

def trigger_phone_call(item_name):
    print(f"\n[🚨] STOCK DETECTED! CALLING @e34song FOR {item_name.upper()}...")
    url = CALL_LINKS.get(item_name)
    try:
        http_get(url, timeout=10)
    except Exception as e:
        print(f"[!] Call failed: {e}")

    for _ in range(5):
        winsound.Beep(2500, 400)
        winsound.Beep(1500, 400)

def mark_backoff(v_id):
    state = BACKOFF[v_id]
    next_delay = state["current"] * 2 if state["current"] else INITIAL_BACKOFF_SECONDS
    next_delay = min(MAX_BACKOFF_SECONDS, next_delay + random.uniform(0.5, 2.0))
    state["current"] = next_delay
    state["cooldown_until"] = time.time() + next_delay

def clear_backoff(v_id):
    BACKOFF[v_id]["current"] = 0.0
    BACKOFF[v_id]["cooldown_until"] = 0.0

def is_in_stock(v_id):
    """Uses curl_cffi to mimic a real Chrome 131 TLS handshake (Bypasses Shopify Bot Detection)"""
    state = BACKOFF[v_id]
    now = time.time()
    if now < state["cooldown_until"]:
        return False

    api_url = f"{VARIANTS[v_id]['url']}.js"
    try:
        # 'impersonate' ensures we look like a real user browser to Shopify's firewall
        r = http_get(api_url, timeout=10)
        if r.status_code in (429, 503):
            mark_backoff(v_id)
            return False
        if r.status_code == 200:
            data = r.json()
            for v in data['variants']:
                if str(v['id']) == v_id and v['available']:
                    clear_backoff(v_id)
                    return True
        clear_backoff(v_id)
    except Exception:
        mark_backoff(v_id)
    return False

def run_strike(v_id):
    info = VARIANTS[v_id]
    trigger_phone_call(info['name'])

    with sync_playwright() as p:
        context = launch_profile(p, headless=False)
        page = new_stealth_page(context)

        print(f"[*] Stock confirmed! Opening checkout for {info['name']}...")
        
        page.goto(info['url'])
        time.sleep(random.uniform(0.8, 1.5))
        
        strike_url = f"https://formdt1.com/cart/add?id={v_id}&quantity=1&return_to=/checkout"
        page.goto(strike_url)

        print(f"\n[!!!] BROWSER READY. CHECKOUT LOADED. PAY NOW!")
        
        while len(context.pages) > 0:
            time.sleep(1)
        
        print("[*] Browser closed. Resuming monitor for the next restock...")

def main(mode="monitor"):
    if mode == "testcall":
        item = sys.argv[2] if len(sys.argv) > 2 else "Titanium"
        trigger_phone_call(item)
        return

    if mode == "warmup":
        with sync_playwright() as p:
            context = launch_profile(p, headless=False)
            page = new_stealth_page(context)
            print("[*] WARMUP: Loading login page...")
            load_login(page)
            print("[*] Log into FormD/Shop Pay in this window, then close it to start monitoring.")
            while len(context.pages) > 0:
                time.sleep(1)
        return

    print("[*] Ghost V5 Monitor Active (Titanium & Silver)...")
    while True:
        for v_id in VARIANTS:
            name = VARIANTS[v_id]['name']
            print(f"[{time.strftime('%H:%M:%S')}] Checking {name}...")
            if is_in_stock(v_id):
                print(f"[{time.strftime('%H:%M:%S')}] {name} IN STOCK! Launching strike...")
                run_strike(v_id)
                time.sleep(30) 
            else:
                print(f"[{time.strftime('%H:%M:%S')}] {name} not in stock.")
            time.sleep(random.uniform(0.4, 1.2))
        
        time.sleep(random.uniform(15, 25))

if __name__ == "__main__":
    cli_mode = sys.argv[1] if len(sys.argv) > 1 else "monitor"
    main(mode=cli_mode)
