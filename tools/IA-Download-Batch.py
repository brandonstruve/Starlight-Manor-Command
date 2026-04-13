import os
import sys
import json
import time
import signal
import requests
from urllib.parse import urljoin, urlparse
from datetime import datetime
from bs4 import BeautifulSoup

# =========================
# CONFIG
# =========================
DOWNLOAD_DIR = r"S:\Downloads\Autodownloader"
LOG_DIR = os.path.join(DOWNLOAD_DIR, "logs")
STATE_FILE = os.path.join(LOG_DIR, "state.json")

SKIP_EXTENSIONS = {".html", ".htm", ".css", ".js"}
CHUNK_SIZE = 1024 * 1024  # 1 MB
RETRY_LIMIT = 3
RETRY_BACKOFF = 5
POLITE_DELAY = 1.0

# =========================
# SETUP
# =========================
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

RUN_LOG = os.path.join(
    LOG_DIR,
    f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
)

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(RUN_LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")

# =========================
# STATE
# =========================
if os.path.exists(STATE_FILE):
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        state = json.load(f)
else:
    state = {}

def save_state():
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)

def handle_exit(sig, frame):
    log("Interrupted — saving state.")
    save_state()
    sys.exit(0)

signal.signal(signal.SIGINT, handle_exit)

# =========================
# UTILITIES
# =========================
def format_bytes(n):
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if n < 1024:
            return f"{n:.2f} {unit}"
        n /= 1024
    return f"{n:.2f} PB"

def progress_bar(cur, total, width=30):
    if total <= 0:
        return "[??????????????????????????????]"
    filled = int(width * cur / total)
    return "[" + "█" * filled + "-" * (width - filled) + "]"

def is_real_file(href):
    if not href:
        return False
    if href.endswith("/"):
        return False
    filename = os.path.basename(urlparse(href).path)
    if not filename:
        return False
    if "." not in filename:
        return False
    ext = os.path.splitext(filename.lower())[1]
    if ext in SKIP_EXTENSIONS:
        return False
    return True

# =========================
# SCRAPE
# =========================
def get_file_list(base_url):
    log(f"Fetching file list from {base_url}")
    r = requests.get(base_url)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    files = []

    for link in soup.find_all("a"):
        href = link.get("href")
        if not is_real_file(href):
            continue

        full_url = urljoin(base_url + "/", href)
        filename = os.path.basename(urlparse(full_url).path)
        files.append((filename, full_url))

    log(f"Filtered to {len(files)} real files")
    return files

# =========================
# VALIDATION
# =========================
def head_validate(url):
    h = requests.head(url, allow_redirects=True)
    if h.status_code not in (200, 206):
        return None
    ctype = h.headers.get("Content-Type", "").lower()
    if ctype.startswith("text/html"):
        return None
    size = int(h.headers.get("Content-Length", 0))
    if size <= 0:
        return None
    accept_ranges = h.headers.get("Accept-Ranges", "").lower() == "bytes"
    return size, accept_ranges

# =========================
# DOWNLOAD
# =========================
def download_file(filename, url):
    dest = os.path.join(DOWNLOAD_DIR, filename)
    part = dest + ".part"

    head = head_validate(url)
    if not head:
        log(f"Skipping non-file endpoint: {filename}")
        return

    total_size, can_resume = head
    downloaded = 0
    headers = {}

    if os.path.exists(part) and can_resume:
        downloaded = os.path.getsize(part)
        if downloaded < total_size:
            headers["Range"] = f"bytes={downloaded}-"
        else:
            downloaded = 0

    if os.path.exists(dest) and os.path.getsize(dest) == total_size:
        log(f"Skipping (already complete): {filename}")
        state[filename] = {"url": url, "size": total_size, "status": "complete"}
        save_state()
        return

    log(f"Downloading: {filename}")
    start = time.time()

    with requests.get(url, headers=headers, stream=True) as r:
        r.raise_for_status()
        mode = "ab" if headers else "wb"

        with open(part, mode) as f:
            for chunk in r.iter_content(chunk_size=CHUNK_SIZE):
                if not chunk:
                    continue
                f.write(chunk)
                downloaded += len(chunk)

                elapsed = max(time.time() - start, 0.1)
                speed = downloaded / elapsed
                pct = downloaded / total_size * 100

                print(
                    "\r"
                    f"{progress_bar(downloaded, total_size)} "
                    f"{pct:6.2f}% "
                    f"{format_bytes(downloaded)} / {format_bytes(total_size)} "
                    f"{format_bytes(speed)}/s",
                    end="",
                    flush=True
                )

    print()
    os.replace(part, dest)
    log(f"Completed: {filename}")

    state[filename] = {"url": url, "size": total_size, "status": "complete"}
    save_state()

# =========================
# MAIN
# =========================
def main():
    url = input("Paste Archive.org download URL: ").strip()
    if not url:
        print("No URL provided.")
        return

    try:
        files = get_file_list(url)
    except Exception as e:
        log(f"Failed to fetch file list: {e}")
        return

    for filename, file_url in files:
        attempts = 0
        while attempts < RETRY_LIMIT:
            try:
                download_file(filename, file_url)
                break
            except Exception as e:
                attempts += 1
                log(f"Error downloading {filename}: {e}")
                if attempts < RETRY_LIMIT:
                    log(f"Retrying in {RETRY_BACKOFF}s...")
                    time.sleep(RETRY_BACKOFF)
                else:
                    log(f"Failed permanently: {filename}")
        time.sleep(POLITE_DELAY)

    log("All downloads processed.")

if __name__ == "__main__":
    main()
