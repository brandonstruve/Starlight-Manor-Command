import os
from collections import Counter

# --- CONFIGURATION ---
FILE_PATH = r"C:\Shortcut Hub\Toolbox\data\library_dump.txt"
DELIMITER = "|||"  # Your triple-pipe separator
# ---------------------

def run_starlight_audit():
    if not os.path.exists(FILE_PATH):
        print(f"Error: {FILE_PATH} not found.")
        return

    niche_counts = Counter()
    total_tracks = 0
    
    # Handling potential encoding issues from Windows Clipboard
    try:
        with open(FILE_PATH, 'r', encoding='utf-16') as f:
            lines = f.readlines()
    except:
        with open(FILE_PATH, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()

    for line in lines:
        if not line.strip(): continue
        
        # Split by <Artist>|||<Title>|||<Niche>
        parts = line.split(DELIMITER)
        
        if len(parts) >= 3:
            total_tracks += 1
            raw_niche = parts[2].strip()
            
            if raw_niche:
                # Split multi-tags if they are semicolon-separated within the field
                tags = [t.strip() for t in raw_niche.split(';') if t.strip()]
                for tag in tags:
                    niche_counts[tag] += 1

    # --- ADJUSTMENT LOGIC ---
    # Subtract 1 from every found niche to account for the "Master Placeholder" track
    adjusted_counts = {niche: count - 1 for niche, count in niche_counts.items()}
    
    # Filter out anything that dropped to 0 or less (not yet started)
    active_niches = {k: v for k, v in adjusted_counts.items() if v > 0}

    print("\n" + "="*45)
    print(" STARLIGHT MANOR: REAL-WORLD INVENTORY")
    print(" (Excluding Placeholder Track)")
    print("="*45)
    
    # Sort by count (Highest first)
    sorted_niches = sorted(active_niches.items(), key=lambda x: x[1], reverse=True)
    
    if not sorted_niches:
        print("No niches found beyond the placeholder track.")
    else:
        for niche, count in sorted_niches:
            print(f"{niche.ljust(25)}: {count}")
        
    print("-" * 45)
    print(f"Total Tracks in File:   {total_tracks}")
    print(f"Active Niches:          {len(active_niches)}")
    print("="*45)

if __name__ == "__main__":
    run_starlight_audit()