import os
import csv
import requests
from dotenv import load_dotenv

ENV_PATH = r"C:\Starlight Manor Command\config\.env"
OUTPUT_CSV = "immich_people_raw.csv"

def extract_immich_people():
    if os.path.exists(ENV_PATH):
        load_dotenv(ENV_PATH)
    else:
        print(f"❌ Error: .env file not found at {ENV_PATH}")
        return

    api_base_url = os.getenv("IMMICH_API_URL")
    api_key = os.getenv("IMMICH_API_KEY")

    if not api_base_url or not api_key:
        print("❌ Error: Missing URL or Key in .env")
        return

    # INTERNAL FIX: Append /api only for this request
    base_url = api_base_url.rstrip('/')
    target_url = f"{base_url}/api/people" if not base_url.endswith('/api') else f"{base_url}/people"
    
    headers = {"Accept": "application/json", "x-api-key": api_key}

    print(f"🔄 Connecting to: {target_url}")

    try:
        response = requests.get(target_url, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        people_list = data.get('people', []) if isinstance(data, dict) else data

        with open(OUTPUT_CSV, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            # Added Birthdate column
            writer.writerow(['Immich_ID', 'Name', 'Birthdate'])
            for person in people_list:
                name = person.get('name') or "Unnamed Person"
                # Extract birthDate (returns None if not set)
                birthdate = person.get('birthDate') or ""
                writer.writerow([person.get('id'), name, birthdate])

        print(f"✅ Success! Extracted {len(people_list)} people to {OUTPUT_CSV}")

    except Exception as e:
        print(f"❌ Connection error: {e}")

if __name__ == "__main__":
    extract_immich_people()