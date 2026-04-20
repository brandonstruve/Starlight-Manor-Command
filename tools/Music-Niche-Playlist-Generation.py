import os
import random
import xml.etree.ElementTree as ET
from urllib.parse import unquote
from collections import Counter

# --- CONFIGURATION ---
DATA_DIR = r"C:\Starlight Manor Command\tools\data"
COLOR_FILE = os.path.join(DATA_DIR, "colors.txt")
ROTATION_FILE = os.path.join(DATA_DIR, "rotation.txt")
HISTORY_LOG = os.path.join(DATA_DIR, "history.log")
OUTPUT_DIR = r"C:\Users\brand\Music\MusicBee\Playlists\Palette of BS"

# --- THE PERMANENT MANIFESTS ---
MANIFESTS = {
    1: ['Opener', 'ScoreLight', 'RetroBit', 'Modern', 'ParkScore', 'TVTheme', '90s', 'Chaos', '80s', 'ModernBit', 'SoloPiano', 'ScoreHeavy', 'Parody', 'HighVibe', 'Classical', 'Showstopper', 'ModernBway', 'SaveRoom', 'Ambience', 'LowKey', '60s', 'Covers', '70s', 'ParkSong', 'ScoreLight', 'Finale'],
    2: ['Opener', 'SaveRoom', '80s', 'ClassicBway', 'BossBattle', 'ParkSong', 'RetroBit', 'MovieSong', 'ScoreHeavy', 'LowKey', 'HighVibe', 'ModernBway', 'Showstopper', '70s', 'ScoreLight', '00s', 'Chaos', 'DisneyMovie', 'ModernBit', 'IWant', 'RockOpera', 'Childhood', 'JazzLounge', 'Covers', 'ParkScore', 'Finale'],
    3: ['Opener', 'Exotica', 'ModernBit', '70s', 'ParkSong', 'ScoreLight', 'Chaos', 'BossBattle', 'Parody', 'ScoreHeavy', 'ParkScore', 'TVTheme', 'RetroBit', 'LowKey', 'Camp', 'MovieSong', '80s', '90s', 'Classical', 'Choral', '60s', 'Covers', 'Oldies', 'BigBand', 'ParkSpectacle', 'Finale'],
    4: ['Opener', 'HighVibe', 'ModernBit', 'SaveRoom', '80s', 'ParkScore', 'RetroBit', 'ScoreHeavy', '70s', 'ClassicBway', '00s', '60s', 'RockOpera', 'ScoreLight', 'Chaos', 'ParkSong', 'ModernBway', 'Showstopper', 'LowKey', 'BossBattle', 'MovieSong', 'Covers', 'IWant', 'ScoreMid', 'DisneyMovie', 'Finale'],
    5: ['Opener', 'Classical', 'ModernBway', 'Exotica', 'TVTheme', 'ParkScore', 'ScoreLight', 'DisneyMovie', 'Camp', 'Parody', 'MovieSong', 'RetroBit', '90s', 'Chaos', 'Childhood', 'IWant', '60s', 'ScoreHeavy', 'ClassicBway', 'Choral', 'Showstopper', '90s', 'TVTheme', 'Parody', 'Classical', 'Finale']
}

def find_library_xml():
    search_paths = [
        r"M:\Music\MusicBee\iTunes Music Library.xml",
        r"C:\Users\brand\Music\MusicBee\iTunes Music Library.xml",
        os.path.join(os.environ['USERPROFILE'], "Music", "MusicBee", "iTunes Music Library.xml")
    ]
    for path in search_paths:
        if os.path.exists(path):
            return path
    return None

def load_data():
    played = set()
    if os.path.exists(HISTORY_LOG):
        with open(HISTORY_LOG, 'r', encoding='utf-8-sig', errors='ignore') as f:
            played = set(line.strip() for line in f)

    xml_path = find_library_xml()
    if not xml_path:
        print("Error: Could not locate 'iTunes Music Library.xml'.")
        return None, None

    print(f"Syncing from: {xml_path}")
    pool = {}
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        tracks_dict = root.find("./dict/dict")
        
        if tracks_dict is None:
            return None, None

        for track_entry in tracks_dict.findall("dict"):
            data = {}
            for i in range(0, len(track_entry), 2):
                key = track_entry[i].text
                # Handle cases where the value tag might not follow the key tag immediately
                if i+1 < len(track_entry):
                    val = track_entry[i+1].text
                    data[key] = val

            raw_path = data.get("Location")
            if not raw_path: continue
            
            clean_path = unquote(raw_path.replace("file://localhost/", "").replace("file:///", ""))
            clean_path = clean_path.replace("/", "\\")

            # MAPPING FIX: Explicitly looking for the 'Niche' key you found in your XML
            niche_str = data.get("Niche") or data.get("Grouping") or data.get("Comments")

            if not niche_str or clean_path in played or "Unknown Niche" in niche_str:
                continue

            for n in [x.strip() for x in niche_str.split(';')]:
                if n not in pool: pool[n] = []
                pool[n].append(clean_path)

    except Exception as e:
        print(f"XML Error: {e}")
        return None, None
            
    return pool, played

def get_day():
    if not os.path.exists(ROTATION_FILE): return 1
    with open(ROTATION_FILE, 'r') as f:
        val = f.read().strip()
        return int(val) if val.isdigit() else 1

def run_audit(pool):
    try:
        goal = int(input("\nHow many playlists to plan for? "))
    except ValueError: return
    current_day = get_day()
    total_needed = Counter()
    temp_day = current_day
    for _ in range(goal):
        total_needed.update(MANIFESTS[temp_day])
        temp_day = 1 if temp_day >= 5 else temp_day + 1
    
    print("\n" + "="*45 + f"\n STARLIGHT SHOPPING LIST (Goal: {goal})\n" + "="*45)
    shortfalls = 0
    for niche, needed in sorted(total_needed.items()):
        have = len(pool.get(niche, []))
        if have < needed:
            print(f"{niche.ljust(18)} | {str(have).rjust(5)} | {str(needed).rjust(5)} | ADD {needed-have}")
            shortfalls += 1
    if shortfalls == 0: print("\nInventory is 100% ready!")
    print("="*45 + "\n")

def run_generator(pool):
    if not os.path.exists(COLOR_FILE): return
    with open(COLOR_FILE, 'r', encoding='utf-8') as f:
        color_lines = f.readlines()

    day_slot, new_history, generated = get_day(), [], 0
    while True:
        color_name, color_idx = None, -1
        for i, line in enumerate(color_lines):
            if line.strip() and not line.strip().endswith("[USED]"):
                color_name, color_idx = line.strip(), i
                break
        if not color_name: break

        current_manifest = MANIFESTS[day_slot]
        if not all(pool.get(n) for n in current_manifest):
            print(f"HALTED: Insufficient tracks for Slot {day_slot}.")
            break

        tracks = []
        for niche in current_manifest:
            choice = random.choice(pool[niche])
            for n in pool:
                if choice in pool[n]: pool[n].remove(choice)
            tracks.append(choice)
            new_history.append(choice)

        m3u_path = os.path.join(OUTPUT_DIR, f"{color_name}.m3u")
        with open(m3u_path, 'w', encoding='utf-8') as m3u:
            m3u.write("#EXTM3U\n" + "\n".join(tracks))

        color_lines[color_idx] = f"{color_name} [USED]\n"
        print(f"Generated: {color_name}.m3u (Slot: {day_slot})")
        day_slot = 1 if day_slot >= 5 else day_slot + 1
        generated += 1

    with open(COLOR_FILE, 'w', encoding='utf-8') as f: f.writelines(color_lines)
    with open(ROTATION_FILE, 'w', encoding='utf-8') as f: f.write(str(day_slot))
    if new_history:
        with open(HISTORY_LOG, 'a', encoding='utf-8') as f:
            for t in new_history: f.write(f"{t}\n")
    print(f"\nCreated {generated} playlists.")

if __name__ == "__main__":
    print("STARLIGHT MANOR ENGINE v4.3 (Custom-Key-Fix)")
    pool, _ = load_data()
    if pool:
        choice = input("\n1) Audit\n2) Generate\n\nSelect: ")
        if choice == '1': run_audit(pool)
        elif choice == '2': run_generator(pool)