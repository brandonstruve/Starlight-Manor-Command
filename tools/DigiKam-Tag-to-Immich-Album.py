import sqlite3
import requests
import csv
import os
import time
import sys
from datetime import datetime

# --- CONFIGURATION ---
MAPPING_CSV = r"C:\Shortcut Hub\Toolbox\data\DigiKam-Tag-to-Immich-Album-mapping.csv"
DB_PATH = r"C:\Users\brand\Pictures\digikam4.db"
LOG_DIR = r"C:\Shortcut Hub\Toolbox\logs"
IMMICH_BASE_URL = "http://192.168.68.163:2283/api"
IMMICH_API_KEY = "vzMRFhzZPeC74FJ6ZMyFT4aOV1t2P7BWKTsKwc37A"
BATCH_SIZE = 100

# UUID Mapping for the "Orlando Trash" Logic
ALBUM_IDS = {
    "MAIN": "d533679c-3c8e-4bcd-9938-009331e076a6",
    "NICK": "cac68df8-afb8-4822-a1de-fd6961295d11",
    "NATALIE": "efdc1af4-81d9-4888-8a82-9c395fd2e0e6"
}

# Reverse lookup to convert UUIDs back to names for the log
ALBUM_NAMES = {v: k for k, v in ALBUM_IDS.items()}

# Define the Multi-Routing Rules
ROUTING_RULES = {
    "#friend":  [ALBUM_IDS["MAIN"], ALBUM_IDS["NICK"], ALBUM_IDS["NATALIE"]],
    "#friendm": [ALBUM_IDS["MAIN"], ALBUM_IDS["NICK"]],
    "#friendh": [ALBUM_IDS["MAIN"], ALBUM_IDS["NATALIE"]]
}

def print_progress_bar(iteration, total, prefix='', suffix='', length=50, fill='█'):
    percent = ("{0:.1f}").format(100 * (iteration / float(total)))
    filled_length = int(length * iteration // total)
    bar = fill * filled_length + '-' * (length - filled_length)
    sys.stdout.write(f'\r{prefix} |{bar}| {percent}% {suffix}')
    sys.stdout.flush()

def get_filenames_from_digikam(tag_name):
    try:
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        cursor = conn.cursor()
        query = """
            SELECT i.name FROM Images i
            JOIN ImageTags it ON i.id = it.imageid
            JOIN Tags t ON it.tagid = t.id
            WHERE t.name = ?;
        """
        cursor.execute(query, (tag_name,))
        files = [row[0] for row in cursor.fetchall()]
        conn.close()
        return files
    except Exception as e:
        print(f"\n   ❌ SQLite Error: {e}")
        return []

def run_sync(collection):
    tag = collection['tag']
    friendly_name = collection['friendly_name']
    
    # Determine which albums this tag targets
    target_album_ids = ROUTING_RULES.get(tag, [collection['album'].split('/')[-1]])
    
    # 1. Get filenames
    filenames = get_filenames_from_digikam(tag)
    if not filenames:
        print(f"\nNo files found for tag '{tag}' in digiKam.")
        return

    # 2. Confirmation Step
    print("\n" + "!"*40)
    print(f" PRE-SYNC CONFIRMATION: {friendly_name}")
    print("!"*40)
    print(f" > Tag found: {tag}")
    print(f" > Files to process: {len(filenames)}")
    print(f" > This will sync to {len(target_album_ids)} Immich Album(s):")
    for aid in target_album_ids:
        print(f"   - {ALBUM_NAMES.get(aid, aid)}")
    
    confirm = input("\nProceed with sync? (Y/N): ").strip().lower()
    if confirm != 'y':
        print("Sync cancelled.")
        return

    # 3. Execution
    with requests.Session() as session:
        session.headers.update({"x-api-key": IMMICH_API_KEY, "Content-Type": "application/json"})
        
        found_ids = []
        successful_filenames = []
        print(f"\nStep 1/2: Mapping filenames to Immich IDs...")
        for i, fname in enumerate(filenames):
            try:
                r = session.post(f"{IMMICH_BASE_URL}/search/metadata", json={"originalFileName": fname})
                items = r.json().get("assets", {}).get("items", [])
                if items:
                    found_ids.append(items[0]['id'])
                    successful_filenames.append(fname)
            except:
                pass
            print_progress_bar(i + 1, len(filenames), prefix='   Search:', suffix=f'({i+1}/{len(filenames)})', length=40)

        if found_ids:
            print(f"\n\nStep 2/2: Injecting into {len(target_album_ids)} album(s)...")
            for album_id in target_album_ids:
                total_batches = (len(found_ids) + BATCH_SIZE - 1) // BATCH_SIZE
                for i in range(0, len(found_ids), BATCH_SIZE):
                    chunk = found_ids[i:i + BATCH_SIZE]
                    session.put(f"{IMMICH_BASE_URL}/albums/{album_id}/assets", json={"ids": chunk})
                    current_batch = (i // BATCH_SIZE) + 1
                    print_progress_bar(current_batch, total_batches, prefix=f'   Album {album_id[:8]}...:', length=30)
                print() # Newline after each album finish
                
            # 4. Logging
            print(f"\nWriting to log...")
            os.makedirs(LOG_DIR, exist_ok=True)
            log_path = os.path.join(LOG_DIR, "immich_sync.log")
            
            with open(log_path, "a", encoding="utf-8") as log_file:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                for album_id in target_album_ids:
                    album_name = ALBUM_NAMES.get(album_id, friendly_name)
                    for fname in successful_filenames:
                        log_file.write(f"{timestamp} | Album: {album_name.ljust(15)} | File: {fname}\n")

    print(f"\n✅ SUCCESS: Asset sync complete for '{friendly_name}'.")

def main():
    collections = []
    with open(MAPPING_CSV, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        collections = list(reader)

    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print("="*60)
        print(" DigiKam-to-Immich Split-Era Sync Portal")
        print("="*60)
        for idx, col in enumerate(collections):
            print(f" [{idx + 1}] {col['friendly_name']} ({col['tag']})")
        print(" [Q] Quit")
        print("-" * 60)
        
        choice = input("Choice > ").strip().lower()
        if choice == 'q': break
        
        try:
            index = int(choice) - 1
            if 0 <= index < len(collections):
                run_sync(collections[index])
                input("\nPress Enter to return to menu...")
            else:
                print("Invalid selection.")
                time.sleep(1)
        except ValueError:
            print("Please enter a number.")
            time.sleep(1)

if __name__ == "__main__":
    main()