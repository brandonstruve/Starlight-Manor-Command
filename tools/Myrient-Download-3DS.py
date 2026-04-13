import os
import requests
import zipfile
import py7zr
import logging
import shutil
from bs4 import BeautifulSoup
from tqdm import tqdm
from urllib.parse import unquote, urljoin

# --- CONFIGURATION ---
BASE_URL = "https://myrient.erista.me/files/No-Intro/Nintendo%20-%20Nintendo%203DS%20%28Decrypted%29/"
TARGET_DIR = r"E:\roms\n3ds"
TEMP_DIR = r"E:\roms\n3ds\temp_dl" 
LOG_FILE = r"C:\Shortcut Hub\Toolbox\logs\myrient_3ds_log.txt"
MIN_FREE_GB = 30  # 3DS decrypted files are large; increased buffer
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
    print(f"Scraping Myrient for (USA) Decrypted titles...")
    try:
        response = session.get(BASE_URL, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        links = []
        
        all_anchors = soup.find_all('a', href=True)
        for a in all_anchors:
            href = a['href']
            # Decode to handle the heavy URL encoding on Myrient
            decoded_href = unquote(href).lower()
            
            # Filter for USA and common compressed formats
            if '(usa)' in decoded_href and any(ext in decoded_href for ext in ['.zip', '.7z']):
                if not href.startswith('?'):
                    links.append(urljoin(BASE_URL, href))
        
        links = list(dict.fromkeys(links))
        print(f"Filtered down to {len(links)} (USA) archives.")
        return links
    except Exception as e:
        logging.error(f"Scrape failed: {e}")
        return []

def download_and_extract(session, file_url):
    if not check_disk_space():
        exit()

    encoded_name = file_url.split('/')[-1]
    file_name = unquote(encoded_name)
    
    # State Check: Skip if the extracted file/folder already exists
    # Decrypted 3DS files usually end in .3ds or .cia
    base_name = os.path.splitext(file_name)[0]
    if any(f.startswith(base_name) for f in os.listdir(TARGET_DIR)):
        return 

    archive_path = os.path.join(TEMP_DIR, file_name)

    try:
        # Download
        response = session.get(file_url, stream=True, timeout=60)
        response.raise_for_status()
        total_size = int(response.headers.get('content-length', 0))
        
        with open(archive_path, 'wb') as f, tqdm(
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

        # Extraction Logic
        print(f"  Extacting {file_name}...")
        if archive_path.endswith('.zip'):
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                zip_ref.extractall(TARGET_DIR)
        elif archive_path.endswith('.7z'):
            with py7zr.SevenZipFile(archive_path, mode='r') as archive:
                archive.extractall(path=TARGET_DIR)
        
        logging.info(f"Successfully processed: {file_name}")
        
    except Exception as e:
        logging.error(f"Error processing {file_name}: {e}")
        print(f"\n  [!] Failed {file_name}: {e}")
    finally:
        if os.path.exists(archive_path):
            os.remove(archive_path)

def main():
    with requests.Session() as session:
        # Myrient appreciates a standard User-Agent
        session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        game_links = get_usa_games(session)
        
        if not game_links:
            return

        if DRY_RUN:
            print(f"DRY RUN: Found {len(game_links)} games.")
            return

        for link in tqdm(game_links, desc="Overall 3DS Decrypted Progress", unit="game"):
            download_and_extract(session, link)

if __name__ == "__main__":
    main()