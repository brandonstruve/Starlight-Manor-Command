import sqlite3
import requests
import os
from dotenv import load_dotenv
from pathlib import Path

# --- Configuration & Paths ---
ENV_PATH = Path(r"C:\Starlight Manor Command\config\.env")
DB_PATH = Path(r"C:\Starlight Manor Command\data\starlight_manor.db")

# Load environment variables
if not ENV_PATH.exists():
    print(f"Error: .env file not found at {ENV_PATH}")
    exit(1)

load_dotenv(dotenv_path=ENV_PATH)

IMMICH_URL = os.getenv("IMMICH_API_URL")
IMMICH_KEY = os.getenv("IMMICH_API_KEY")

if not IMMICH_URL or not IMMICH_KEY:
    print("Error: IMMICH_API_URL or IMMICH_API_KEY not found in .env file.")
    exit(1)

IMMICH_URL = IMMICH_URL.rstrip('/')

def update_immich_counts():
    if not DB_PATH.exists():
        print(f"Error: Could not find Database at {DB_PATH}")
        return

    # Initialize session to reuse TCP connections (drastically speeds up requests)
    session = requests.Session()
    session.headers.update({"x-api-key": IMMICH_KEY, "Accept": "application/json"})

    print("🔌 Connecting to Starlight Manor Database...")
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Only pull records that actually have an Immich ID to save processing time
        cursor.execute("SELECT id, immich_id FROM People WHERE immich_id IS NOT NULL AND immich_id != ''")
        people = cursor.fetchall()
        
        print(f"🚀 Starting update for {len(people)} records with Immich IDs...")

        updates_made = 0
        errors = 0
        not_found = 0
        
        # Store our successfully retrieved counts here: [(asset_count, db_id), ...]
        updates_batch = []

        for db_id, immich_id in people:
            person_id_str = str(immich_id).strip()

            try:
                # Using the statistics endpoint
                endpoint = f"{IMMICH_URL}/api/people/{person_id_str}/statistics"
                response = session.get(endpoint, timeout=15)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Extract the 'assets' value, default to 0 if something is weird
                    asset_count = int(data.get('assets', 0))
                    
                    updates_batch.append((asset_count, db_id))
                    updates_made += 1
                    
                    if updates_made % 50 == 0:
                        print(f"Progress: {updates_made} counts retrieved...")
                        
                elif response.status_code == 404:
                    # The ID exists in the DB but not in Immich
                    not_found += 1
                else:
                    print(f"Warning: ID {person_id_str} returned status {response.status_code}")
                    errors += 1

            except Exception as e:
                print(f"Error fetching ID {person_id_str}: {e}")
                errors += 1

        # Execute the database updates in one quick batch
        if updates_batch:
            print("💾 Writing updates to the database...")
            cursor.executemany("UPDATE People SET asset_count = ? WHERE id = ?", updates_batch)
            conn.commit()

        print("-" * 30)
        print("✨ Update Complete!")
        print(f"Successfully updated: {updates_made}")
        print(f"IDs not found (404s): {not_found}")
        print(f"Other errors/warnings: {errors}")
        print("-" * 30)

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        if 'conn' in locals() and conn:
            conn.close()

if __name__ == "__main__":
    update_immich_counts()