import os
import requests
import zipfile
import logging
import shutil
from bs4 import BeautifulSoup
from tqdm import tqdm
from urllib.parse import unquote, urljoin

# --- CONFIGURATION ---
BASE_URL = "https://myrient.erista.me/files/Redump/Nintendo%20-%20Wii%20-%20NKit%20RVZ%20%5Bzstd-19-128k%5D/"
TARGET_DIR = r"E:\roms\wii"
TEMP_DIR = r"E:\roms\wii\temp_dl" 
LOG_FILE = r"C:\Shortcut Hub\Toolbox\logs\myrient_wii_log.txt"
MIN_FREE_GB = 10  # Script will pause if E: drive has less than 10GB free
DRY_RUN = False 

# Ensure directories exist
os.makedirs(TARGET_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def check_disk_space():
    total, used, free = shutil.disk_usage("E:\\")
    free_gb = free // (2**30)
    if free_gb < MIN_FREE_GB:
        print(f"\n[!] WARNING: Low Disk Space! Only {free_gb}GB remaining on E:. Powering down...")
        logging.error(f"Low disk space on E: ({free_gb}GB). Script stopped.")
        return False
    return True

def get_usa_games(session):
    print(f"Scraping Myrient for (USA) titles...")
    try:
        response = session.get(BASE_URL, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        links = []
        
        all_anchors = soup.find_all('a', href=True)
        for a in all_anchors:
            href = a['href']
            decoded_href = unquote(href).lower()
            link_text = a.get_text().lower()

            if '.zip' in decoded_href and ('(usa)' in decoded_href or '(usa)' in link_text):
                if not href.startswith('?'):
                    links.append(urljoin(BASE_URL, href))
        
        links = list(dict.fromkeys(links))
        print(f"Filtered down to {len(links)} (USA) zip files.")
        return links
    except Exception as e:
        logging.error(f"Scrape failed: {e}")
        return []

def download_and_extract(session, file_url):
    if not check_disk_space():
        exit()

    encoded_name = file_url.split('/')[-1]
    file_name = unquote(encoded_name)
    
    # State Check: Skip if the extracted file already exists
    base_name = file_name.replace('.zip', '')
    if any(f.startswith(base_name) for f in os.listdir(TARGET_DIR) if not f.endswith('.zip')):
        return 

    zip_path = os.path.join(TEMP_DIR, file_name)

    try:
        response = session.get(file_url, stream=True, timeout=60)
        response.raise_for_status()
        total_size = int(response.headers.get('content-length', 0))
        
        with open(zip_path, 'wb') as f, tqdm(
            desc=file_name[:40].ljust(40), 
            total=total_size,
            unit='iB',
            unit_scale=True,
            unit_divisor=1024,
            leave=False
        ) as bar:
            for data in response.iter_content(chunk_size=1024*1024):
                size = f.write(data)
                bar.update(size)

        # Extraction
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            for member in zip_ref.namelist():
                zip_ref.extract(member, TARGET_DIR)
                logging.info(f"Extracted to E: {member}")
        
    except Exception as e:
        logging.error(f"Error processing {file_name}: {e}")
        print(f"\n  [!] Failed {file_name}: {e}")
    finally:
        if os.path.exists(zip_path):
            os.remove(zip_path)

def main():
    with requests.Session() as session:
        session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        game_links = get_usa_games(session)
        
        if not game_links:
            return

        if DRY_RUN:
            print(f"DRY RUN: Found {len(game_links)} games.")
            return

        for link in tqdm(game_links, desc="Overall E:\ Library Progress", unit="game"):
            download_and_extract(session, link)

if __name__ == "__main__":
    main()