#!/usr/bin/env python3
"""
Simple Chain Daily Bot By DEGIO — https://task.simplechain.com/

Usage:
  python bot.py            # run once
  python bot.py --loop     # run daily (end time + 24 hours)

keys.txt   — one private key per line
proxy.txt  — one proxy per line (optional)

Supported proxy formats:
  http://host:port
  https://host:port
  socks4://host:port
  socks5://host:port
  http://user:pass@host:port
  socks5://user:pass@host:port
  host:port                  (treated as http://)
  user:pass@host:port        (treated as http://)
"""

import os
import sys
import time
import argparse
import logging
from datetime import datetime, timedelta
from typing import Optional

import requests
import pytz
from colorama import Fore, Style, init
from eth_account import Account
from eth_account.messages import encode_defunct

init(autoreset=True)
logging.basicConfig(level=logging.WARNING)

# ─── Config ───────────────────────────────────────────────────────────────────

BASE_URL   = "https://task.simplechain.com"
KEYS_FILE  = "keys.txt"
PROXY_FILE = "proxy.txt"

MYANMAR_TZ = pytz.timezone("Asia/Rangoon")

DELAY_BETWEEN_WALLETS = 3
DELAY_BETWEEN_TASKS   = 2

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/146.0.0.0 Safari/537.36")

TASK_VISIT   = "ACCESS_LINK"
TASK_CHECKIN = "DAILY_CHECK_IN"
DONE_STATUSES = {"COMPLETED_TODAY", "COMPLETED"}

W = 54  # display width

# ─── Display helpers ──────────────────────────────────────────────────────────

C  = Fore.CYAN
G  = Fore.GREEN
Y  = Fore.YELLOW
R  = Fore.RED
W_ = Style.RESET_ALL

def line(char="═"):
    print(f"{C}{char * W}{W_}")

def banner():
    title = "Simple Chain Daily Bot By DEGIO"
    pad   = max(0, (W - len(title)) // 2)
    print(f"\n{C}{'═' * W}")
    print(f"{C}{' ' * pad}{title}")
    print(f"{C}{'═' * W}{W_}\n")

def status_str(s: str) -> str:
    if s == "success":
        return f"{G}Success{W_}"
    elif s == "already":
        return f"{Y}Already Done{W_}"
    elif s == "skip":
        return f"{Y}Skipped{W_}"
    elif s == "not_found":
        return f"{Y}Not Found{W_}"
    else:
        return f"{R}Failed{W_}"

def print_row(label: str, value: str):
    print(f"  {label:<10}: {value}")

# ─── Proxy / Session ─────────────────────────────────────────────────────────

KNOWN_SCHEMES = ("http://", "https://", "socks4://", "socks5://", "socks5h://", "socks4a://")


def normalize_proxy(raw: str) -> str:
    """
    Normalize a proxy string to a full URL that requests/PySocks understands.

    Accepted inputs (examples):
      1.2.3.4:8080                     → http://1.2.3.4:8080
      user:pass@1.2.3.4:8080           → http://user:pass@1.2.3.4:8080
      http://1.2.3.4:8080              → unchanged
      socks5://user:pass@1.2.3.4:1080  → unchanged
    """
    raw = raw.strip()
    lower = raw.lower()
    if any(lower.startswith(s) for s in KNOWN_SCHEMES):
        return raw
    # no scheme — prepend http://
    return "http://" + raw


def load_proxies(path: str) -> list:
    if not os.path.exists(path):
        return []
    proxies = []
    with open(path) as f:
        for line_ in f:
            line_ = line_.strip()
            if line_ and not line_.startswith("#"):
                proxies.append(normalize_proxy(line_))
    return proxies


def make_session(proxy: Optional[str] = None) -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "accept": "*/*",
        "accept-language": "en-US,en;q=0.9",
        "content-type": "application/json",
        "origin": BASE_URL,
        "referer": f"{BASE_URL}/",
        "user-agent": UA,
        "sec-ch-ua": '"Chromium";v="146", "Not-A.Brand";v="24", "Google Chrome";v="146"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    })
    if proxy:
        s.proxies = {"http": proxy, "https": proxy}
    return s

# ─── HTTP ─────────────────────────────────────────────────────────────────────

def api_get(session, path: str, token: str) -> dict:
    r = session.get(BASE_URL + path,
                    headers={"authorization": f"Bearer {token}"},
                    timeout=15)
    r.raise_for_status()
    return r.json()


def api_post(session, path: str, body: dict, token: Optional[str] = None) -> dict:
    h = {"authorization": f"Bearer {token}"} if token else {}
    r = session.post(BASE_URL + path, json=body, headers=h, timeout=15)
    r.raise_for_status()
    return r.json()

# ─── Auth ─────────────────────────────────────────────────────────────────────

def wallet_login(session, address: str, private_key: str) -> str:
    r = api_post(session, "/api/v1/get/nonce", {"address": address})
    if r.get("code") != 0:
        raise RuntimeError(f"nonce: {r.get('message')}")

    data = r.get("data", {})

    if isinstance(data, dict) and data.get("message"):
        message = data["message"]
    else:
        nonce = data.get("nonce") if isinstance(data, dict) else data
        message = (
            "Welcome to SimpleChain!\n\n"
            "Click to sign in and accept the SimpleChain Terms of Service.\n\n"
            "This request will not trigger a blockchain transaction or cost any gas fees.\n\n"
            f"Nonce: {nonce}"
        )

    raw_sig = Account.from_key(private_key).sign_message(
        encode_defunct(text=message)).signature.hex()
    sig = raw_sig if raw_sig.startswith("0x") else "0x" + raw_sig

    r2 = api_post(session, "/api/v1/login",
                  {"address": address, "message": message, "signature": sig})
    if r2.get("code") != 0:
        raise RuntimeError(f"login: {r2.get('message')}")

    token = r2.get("data", {}).get("token") or r2.get("data", {}).get("accessToken") or ""
    if not token and isinstance(r2.get("data"), str):
        token = r2["data"]
    if not token:
        raise RuntimeError(f"no token: {r2}")
    return token

# ─── Tasks ────────────────────────────────────────────────────────────────────

def get_tasks(session, token: str) -> list:
    try:
        r = api_get(session, "/api/v1/task/list", token)
        d = r.get("data", {})
        if isinstance(d, dict):
            d = d.get("tasks") or d.get("list") or d.get("items") or []
        return d if isinstance(d, list) else []
    except Exception:
        return []


def do_visit(session, token: str, tasks: list) -> str:
    task = next((t for t in tasks if t.get("taskCode") == TASK_VISIT), None)
    if not task:
        return "not_found"

    if task.get("completionStatus") in DONE_STATUSES:
        return "already"

    task_id = task.get("taskId") or task.get("id") or ""
    if not task_id:
        return "failed"

    try:
        r = api_post(session, "/api/v1/task/complete",
                     {"taskId": task_id}, token=token)
        if r.get("code") == 0:
            return "success"
        if "already" in str(r.get("message", "")).lower():
            return "already"
        return "failed"
    except Exception:
        return "failed"


def do_checkin(session, token: str, tasks: list) -> str:
    task = next((t for t in tasks if t.get("taskCode") == TASK_CHECKIN), None)
    if task and task.get("completionStatus") in DONE_STATUSES:
        return "already"

    try:
        r    = api_post(session, "/api/v1/campaign/checkin", {}, token=token)
        code = r.get("code")
        msg  = r.get("message", "")
        if code == 0:
            return "success"
        if "already" in msg.lower() or "today" in msg.lower() or code in (409, 10001, 10002):
            return "already"
        return "failed"
    except Exception:
        return "failed"

# ─── Single wallet ────────────────────────────────────────────────────────────

def run_wallet(private_key: str, proxy: Optional[str],
               index: int, total: int) -> bool:
    private_key = private_key.strip()
    if not private_key or private_key.startswith("#"):
        return False
    if not private_key.startswith("0x"):
        private_key = "0x" + private_key

    try:
        address = Account.from_key(private_key).address
        short   = address[:6] + "..." + address[-4:]
        trail   = "─" * (W - len(f"  {index}. {short} ") - 1)
        print(f"\n  {C}{index}. {short} {trail}{W_}")

        session = make_session(proxy)

        try:
            token = wallet_login(session, address, private_key)
            print_row("Login", status_str("success"))
        except Exception as e:
            print_row("Login", status_str("failed"))
            print(f"  {R}  └ {e}{W_}")
            return False

        tasks = get_tasks(session, token)

        time.sleep(1)
        v = do_visit(session, token, tasks)
        print_row("Visit", status_str(v))
        time.sleep(DELAY_BETWEEN_TASKS)

        c = do_checkin(session, token, tasks)
        print_row("Check-in", status_str(c))

        return True

    except requests.HTTPError as e:
        print_row("Error", f"{R}HTTP {e.response.status_code}{W_}")
    except Exception as e:
        print_row("Error", f"{R}{e}{W_}")

    return False

# ─── Multi-wallet ─────────────────────────────────────────────────────────────

def load_keys(path: str) -> list:
    if not os.path.exists(path):
        print(f"{R}Error: {path} not found.{W_}")
        print("Create keys.txt with one private key per line.")
        sys.exit(1)
    with open(path) as f:
        return f.readlines()


def run_all(private_keys: list, proxies: list) -> datetime:
    """Run all wallets and return the datetime when the run finished."""
    keys = [k.strip() for k in private_keys
            if k.strip() and not k.strip().startswith("#")]
    if not keys:
        print(f"{R}No valid keys found.{W_}")
        sys.exit(1)

    now_mm = datetime.now(MYANMAR_TZ).strftime("%Y-%m-%d %H:%M:%S")
    print(f"{C}[ {now_mm} ] Starting daily run...{W_}")

    ok = fail = 0
    for i, key in enumerate(keys):
        proxy = proxies[i % len(proxies)] if proxies else None
        if run_wallet(key, proxy, index=i + 1, total=len(keys)):
            ok += 1
        else:
            fail += 1
        if i < len(keys) - 1:
            time.sleep(DELAY_BETWEEN_WALLETS)

    end_time = datetime.now(MYANMAR_TZ)
    next_dt  = end_time + timedelta(hours=24)
    next_str = next_dt.strftime("%Y-%m-%d %H:%M")

    print(f"\n{C}{'═' * W}{W_}")
    print(f"  Done    {G}OK {ok}{W_}  |  {R}Fail {fail}{W_}")
    print(f"  End     {C}{end_time.strftime('%Y-%m-%d %H:%M:%S')}{W_}")
    print(f"  Next    {C}{next_str}  (end + 24h){W_}")
    print(f"{C}{'═' * W}{W_}\n")

    return end_time

# ─── Scheduler ────────────────────────────────────────────────────────────────

def sleep_with_countdown(target: datetime):
    ts = target.strftime("%Y-%m-%d %H:%M")
    print(f"Next run: {C}{ts}{W_}")
    dots = 0
    while True:
        secs = (target - datetime.now(MYANMAR_TZ)).total_seconds()
        if secs <= 0:
            break
        h = int(secs // 3600)
        m = int((secs % 3600) // 60)
        dot_str = " ." * (dots % 4)
        print(f"\rSleeping {h}h {m}m{dot_str}   ", end="", flush=True)
        dots += 1
        time.sleep(60)
    print()


def run_loop(keys_source, proxy_file: str):
    while True:
        keys    = load_keys(keys_source) if isinstance(keys_source, str) else keys_source
        proxies = load_proxies(proxy_file)
        end_time = run_all(keys, proxies)
        target   = end_time + timedelta(hours=24)
        sleep_with_countdown(target)

# ─── Entry point ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Simple Chain Daily Bot By DEGIO")
    kg = parser.add_mutually_exclusive_group()
    kg.add_argument("--key",  metavar="PRIVATE_KEY")
    kg.add_argument("--file", metavar="FILE", default=KEYS_FILE)
    parser.add_argument("--proxy-file", metavar="FILE", default=PROXY_FILE)
    args = parser.parse_args()

    banner()

    if args.key:
        run_loop([args.key], args.proxy_file)
    else:
        run_loop(args.file, args.proxy_file)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{R}Interrupted. Goodbye.{W_}")
        sys.exit(0)
