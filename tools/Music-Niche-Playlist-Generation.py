import os
import random
from collections import Counter

# --- CONFIGURATION ---
INPUT_FILE = r"C:\Shortcut Hub\Toolbox\data\library_dump.txt"
COLOR_FILE = r"C:\Shortcut Hub\Toolbox\data\colors.txt"
ROTATION_FILE = r"C:\Shortcut Hub\Toolbox\data\rotation.txt"
OUTPUT_DIR = r"C:\Users\brand\Music\MusicBee\Playlists\Palette of BS"
HISTORY_LOG = r"C:\Shortcut Hub\Toolbox\data\history.log"

# --- THE PERMANENT MANIFESTS ---
MANIFESTS = {
    1: ['Opener', 'ScoreLight', 'RetroBit', 'Modern', 'ParkScore', 'TVTheme', '90s', 'Chaos', '80s', 'ModernBit', 'SoloPiano', 'ScoreHeavy', 'Parody', 'HighVibe', 'Classical', 'Showstopper', 'ModernBway', 'SaveRoom', 'Ambience', 'LowKey', '60s', 'Covers', '70s', 'ParkSong', 'ScoreLight', 'Finale'],
    2: ['Opener', 'SaveRoom', '80s', 'ClassicBway', 'BossBattle', 'ParkSong', 'RetroBit', 'MovieSong', 'ScoreHeavy', 'LowKey', 'HighVibe', 'ModernBway', 'Showstopper', '70s', 'ScoreLight', '00s', 'Chaos', 'DisneyMovie', 'ModernBit', 'IWant', 'RockOpera', 'Childhood', 'JazzLounge', 'Covers', 'ParkScore', 'Finale'],
    3: ['Opener', 'Exotica', 'ModernBit', '70s', 'ParkSong', 'ScoreLight', 'Chaos', 'BossBattle', 'Parody', 'ScoreHeavy', 'ParkScore', 'TVTheme', 'RetroBit', 'LowKey', 'Camp', 'MovieSong', '80s', '90s', 'Classical', 'Choral', '60s', 'Covers', 'Oldies', 'BigBand', 'ParkSpectacle', 'Finale'],
    4: ['Opener', 'HighVibe', 'ModernBit', 'SaveRoom', '80s', 'ParkScore', 'RetroBit', 'ScoreHeavy', '70s', 'ClassicBway', '00s', '60s', 'RockOpera', 'ScoreLight', 'Chaos', 'ParkSong', 'ModernBway', 'Showstopper', 'LowKey', 'BossBattle', 'MovieSong', 'Covers', 'IWant', 'ScoreMid', 'DisneyMovie', 'Finale'],
    5: ['Opener', 'Classical', 'ModernBway', 'Exotica', 'TVTheme', 'ParkScore', 'ScoreLight', 'DisneyMovie', 'Camp', 'Parody', 'MovieSong', 'RetroBit', '90s', 'Chaos', 'Childhood', 'IWant', '60s', 'ScoreHeavy', 'ClassicBway', 'Choral', 'Showstopper', '90s', 'TVTheme', 'Parody', 'Classical', 'Finale']
}

def load_data():
    played = set()
    if os.path.exists(HISTORY_LOG):
        with open(HISTORY_LOG, 'r', encoding='utf-8-sig', errors='ignore') as f:
            played = set(line.strip() for line in f)

    pool = {}
    if not os.path.exists(INPUT_FILE):
        print(f"Error: {INPUT_FILE} not found.")
        return None, None
        
    with open(INPUT_FILE, 'r', encoding='utf-8-sig', errors='ignore') as f:
        for line in f:
            parts = [p.strip() for p in line.strip().split('|||')]
            if len(parts) < 2: continue
            niche_str, path = parts[0], parts[1]
            if "Unknown Niche" in niche_str: continue
            if path in played: continue
            
            niches = [n.strip() for n in niche_str.split(';')]
            for n in niches:
                if n not in pool: pool[n] = []
                pool[n].append(path)
    return pool, played

def get_day():
    if not os.path.exists(ROTATION_FILE): return 1
    with open(ROTATION_FILE, 'r') as f:
        val = f.read().strip()
        return int(val) if val.isdigit() else 1

def run_audit(pool):
    try:
        goal = int(input("\nHow many playlists do you want to plan for? "))
    except ValueError:
        print("Invalid number.")
        return

    current_day = get_day()
    total_needed = Counter()
    
    # Calculate cumulative need over X days
    temp_day = current_day
    for _ in range(goal):
        total_needed.update(MANIFESTS[temp_day])
        temp_day = 1 if temp_day >= 5 else temp_day + 1
    
    print("\n" + "="*45)
    print(f" STARLIGHT SHOPPING LIST (Goal: {goal} Playlists)")
    print("="*45)
    print(f"{'NICHE'.ljust(18)} | {'HAVE'.rjust(5)} | {'NEED'.rjust(5)} | {'STATUS'}")
    print("-"*45)

    shortfalls = 0
    for niche, needed in sorted(total_needed.items()):
        have = len(pool.get(niche, []))
        if have < needed:
            diff = needed - have
            print(f"{niche.ljust(18)} | {str(have).rjust(5)} | {str(needed).rjust(5)} | ADD {diff}")
            shortfalls += 1
        else:
            # Uncomment below if you want to see everything, not just shortfalls
            # print(f"{niche.ljust(18)} | {str(have).rjust(5)} | {str(needed).rjust(5)} | OK")
            pass

    if shortfalls == 0:
        print("\nInventory is 100% ready for this goal!")
    else:
        print(f"\nAudit complete. {shortfalls} niches require more tracks.")
    print("="*45 + "\n")

def run_generator(pool):
    if not os.path.exists(COLOR_FILE):
        print("Error: colors.txt missing.")
        return
    with open(COLOR_FILE, 'r', encoding='utf-8') as f:
        color_lines = f.readlines()

    day_slot = get_day()
    new_history = []
    generated = 0

    while True:
        color_name, color_idx = None, -1
        for i, line in enumerate(color_lines):
            clean = line.strip()
            if clean and not clean.endswith("[USED]"):
                color_name, color_idx = clean, i
                break
        
        if not color_name:
            print("\nOut of colors.")
            break

        current_manifest = MANIFESTS[day_slot]
        can_build = True
        for niche in current_manifest:
            if not pool.get(niche):
                print(f"\nHALTED: Niche '{niche}' empty. Cannot complete Slot {day_slot}.")
                can_build = False
                break
        if not can_build: break

        # Build
        tracks = []
        for niche in current_manifest:
            choice = random.choice(pool[niche])
            for n in pool:
                if choice in pool[n]: pool[n].remove(choice)
            tracks.append(choice)
            new_history.append(choice)

        # Export
        with open(os.path.join(OUTPUT_DIR, f"{color_name}.m3u"), 'w', encoding='utf-8') as m3u:
            m3u.write("#EXTM3U\n")
            for t in tracks: m3u.write(f"{t}\n")

        color_lines[color_idx] = f"{color_name} [USED]\n"
        print(f"Generated: {color_name}.m3u (Pattern Slot: {day_slot})")
        day_slot = 1 if day_slot >= 5 else day_slot + 1
        generated += 1

    # Save State
    with open(COLOR_FILE, 'w', encoding='utf-8') as f: f.writelines(color_lines)
    with open(ROTATION_FILE, 'w', encoding='utf-8') as f: f.write(str(day_slot))
    if new_history:
        with open(HISTORY_LOG, 'a', encoding='utf-8') as f:
            for t in new_history: f.write(f"{t}\n")
    print(f"\nBatch complete. Created {generated} playlists.")

if __name__ == "__main__":
    print("STARLIGHT MANOR ENGINE v1.3")
    pool, _ = load_data()
    if pool:
        print("\n1) Run Audit & Shopping List")
        print("2) Generate Playlists (Infinity Mode)")
        choice = input("\nSelect Option: ")
        
        if choice == '1':
            run_audit(pool)
        elif choice == '2':
            run_generator(pool)
        else:
            print("Exiting.")