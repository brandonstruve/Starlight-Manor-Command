import sqlite3
import pandas as pd
from pathlib import Path

# --- Paths (Explicitly set to your Windows directory) ---
BASE_DIR = Path(r"C:\Starlight Manor Command")
CSV_PATH = BASE_DIR / "data" / "Starlight_Manor_Master_People.csv"
DB_PATH = BASE_DIR / "data" / "starlight_manor.db"

def parse_name(full_name):
    """Splits a full name into First, Middle, and Last."""
    if not full_name or pd.isna(full_name):
        return "", "", ""
        
    parts = str(full_name).strip().split()
    first_name = parts[0] if len(parts) > 0 else ""
    last_name = parts[-1] if len(parts) > 1 else ""
    middle_name = " ".join(parts[1:-1]) if len(parts) > 2 else ""
    
    return first_name, middle_name, last_name

def parse_address(address_string):
    """Attempts to split '123 Main St, City, ST 12345' into distinct fields."""
    street, city, state, zip_code = "", "", "", ""
    if not address_string or pd.isna(address_string):
        return street, city, state, zip_code
        
    parts = [p.strip() for p in str(address_string).split(',')]
    
    if len(parts) >= 1:
        street = parts[0]
    if len(parts) >= 2:
        city = parts[1]
    if len(parts) >= 3:
        # State and Zip are usually grouped together after the second comma
        state_zip = parts[2].split()
        if len(state_zip) >= 1:
            state = state_zip[0]
        if len(state_zip) >= 2:
            zip_code = state_zip[1]
            
    return street, city, state, zip_code

def setup_database():
    """Creates the SQLite schema with normalized Google Contact fields."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("PRAGMA foreign_keys = ON;")

    # 1. Households Table (Created, but left empty for now)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Households (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        household_name TEXT NOT NULL
    )
    ''')

    # 2. People Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS People (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        household_id INTEGER,
        google_id TEXT,
        first_name TEXT,
        middle_name TEXT,
        last_name TEXT,
        maiden_name TEXT,
        nickname TEXT,
        category TEXT,
        sub_category TEXT,
        immich_id TEXT,
        digikam_id TEXT,
        asset_count INTEGER DEFAULT 0,
        birthdate TEXT,
        deathdate TEXT,
        email TEXT,
        phone TEXT,
        street_address TEXT,
        city TEXT,
        state TEXT,
        zip_code TEXT,
        notes TEXT,
        profile_photo_path TEXT,
        FOREIGN KEY (household_id) REFERENCES Households(id) ON DELETE SET NULL
    )
    ''')

    # 3. Relationships Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Relationships (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        person_a_id INTEGER NOT NULL,
        person_b_id INTEGER NOT NULL,
        relationship_type TEXT NOT NULL,
        anniversary_date TEXT,
        FOREIGN KEY (person_a_id) REFERENCES People(id) ON DELETE CASCADE,
        FOREIGN KEY (person_b_id) REFERENCES People(id) ON DELETE CASCADE
    )
    ''')

    # 4. Campaigns Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Campaigns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        campaign_name TEXT NOT NULL,
        year INTEGER,
        status TEXT
    )
    ''')

    # 5. Campaign Members Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Campaign_Members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        campaign_id INTEGER NOT NULL,
        person_id INTEGER,
        household_id INTEGER,
        status TEXT,
        FOREIGN KEY (campaign_id) REFERENCES Campaigns(id) ON DELETE CASCADE,
        FOREIGN KEY (person_id) REFERENCES People(id) ON DELETE CASCADE,
        FOREIGN KEY (household_id) REFERENCES Households(id) ON DELETE CASCADE
    )
    ''')

    conn.commit()
    return conn

def migrate_data(conn):
    """Extracts CSV data, runs transformations, and loads into SQLite."""
    if not CSV_PATH.exists():
        print(f"❌ Could not find CSV at {CSV_PATH}")
        return

    print("📊 Reading flat CSV data...")
    df = pd.read_csv(CSV_PATH).fillna('')
    cursor = conn.cursor()

    print("🏗️ Building database records...")
    for _, row in df.iterrows():
        raw_name = str(row.get('Name', '')).strip()
        if not raw_name:
            continue
            
        # Transform Name and Address
        first, middle, last = parse_name(raw_name)
        raw_address = str(row.get('Address', '')).strip()
        street, city, state, zip_code = parse_address(raw_address)
        
        category = str(row.get('D_Category', '')).strip()
        sub_category = str(row.get('D_Sub Category', '')).strip()
        
        # Household ID explicitly set to None (Blank slate for future household definitions)
        household_id = None

        # Ensure asset count is a clean integer (strips decimals if present)
        raw_assets = str(row.get('ImmichAssetCount', 0))
        asset_count = int(float(raw_assets)) if raw_assets.replace('.', '', 1).isdigit() else 0

        # Insert Person
        cursor.execute('''
            INSERT INTO People (
                household_id, google_id, first_name, middle_name, last_name, category, sub_category,
                immich_id, digikam_id, asset_count, birthdate, deathdate, 
                email, phone, street_address, city, state, zip_code, profile_photo_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            household_id,
            str(row.get('G_Google_ID', '')).strip(),
            first, middle, last,
            category,
            sub_category,
            str(row.get('I_Immich_ID', '')).strip(),
            str(row.get('D_digiKam_ID', '')).strip(),
            asset_count,
            str(row.get('I_Birthdate', '')).strip(),
            str(row.get('I_DeathDate', '')).strip(),
            str(row.get('Email', '')).strip(),
            str(row.get('Phone', '')).replace('.0', '').strip(),  
            street, city, state, zip_code,
            str(row.get('ProfilePhotoPath', '')).strip()
        ))

    conn.commit()
    
    # Validation output
    cursor.execute("SELECT COUNT(*) FROM People")
    people_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM Households")
    household_count = cursor.fetchone()[0]
    
    print("✅ Migration Complete!")
    print(f"📁 Database saved to: {DB_PATH}")
    print(f"👥 Total People Migrated: {people_count}")
    print(f"🏠 Total Households Created: {household_count} (Blank slate ready for future use)")

if __name__ == '__main__':
    # Ensure the data directory exists
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    
    print("🚀 Starting Starlight Manor DB Migration...")
    
    # If the file exists from a previous run, delete it to ensure a completely fresh start
    if Path(DB_PATH).exists():
        print("🗑️ Removing old database file for a fresh migration...")
        Path(DB_PATH).unlink()
        
    db_conn = setup_database()
    migrate_data(db_conn)
    db_conn.close()
    print("✨ Database is ready to use!")