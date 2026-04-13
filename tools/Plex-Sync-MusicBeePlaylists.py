import os
import time
from dotenv import load_dotenv
from plexapi.server import PlexServer

# --- CONFIG ---
load_dotenv(r"C:\Shortcut Hub\Toolbox\.env")

PLEX_URL = os.getenv("PLEX_URL")
PLEX_TOKEN = os.getenv("PLEX_TOKEN")
M3U_BASE_DIR = r"C:\Users\brand\Music\MusicBee\Playlists"
ART_DIR = r"C:\Users\brand\Music\MusicBee\Playlists\_PLAYLISTART"

MB_PREFIX = "M:\\Music\\"
PLEX_PREFIX = "\\\\SM-NAS-01\\Media\\Music\\"

SYSTEM_EMOJI = "⚙️"
FOLDER_MAP = {
    "Game Night": "🎲", "Starlight Manor BGM": "✨", "Palette of BS": "🎨",
    "One Offs": "📎", "Odysseys": "🚗", "Parties": "🥳", "Holidays": "🎄"
}

def normalize_path(p):
    return p.lower().replace('\\', '/').strip()

def find_art_file(base_name):
    if not os.path.exists(ART_DIR): return None
    for ext in ('.jpg', '.jpeg', '.png', '.webp'):
        path = os.path.join(ART_DIR, f"{base_name}{ext}")
        if os.path.exists(path): return path
    return None

def sync_to_plex():
    report = []
    try:
        plex = PlexServer(PLEX_URL, PLEX_TOKEN)
        music_library = plex.library.section('Music')
        print(f"📡 Connected to: {plex.friendlyName}")
    except Exception as e:
        print(f"❌ Connection Failed: {e}"); return

    # --- INDEXING ---
    print("🧠 Building Plex Path Map (Indexing Tracks)...")
    plex_map = {}
    all_tracks = music_library.search(libtype='track')
    for track in all_tracks:
        try:
            for media in track.media:
                for part in media.parts:
                    plex_map[normalize_path(part.file)] = track
        except AttributeError:
            continue

    all_plex_playlists = plex.playlists()

    for root, dirs, files in os.walk(M3U_BASE_DIR):
        if "_PLAYLISTART" in root: continue
        folder_name = os.path.basename(root)
        emoji = FOLDER_MAP.get(folder_name, "")
        
        for file in files:
            if not file.endswith(".m3u"): continue
            
            playlist_title = file.replace(".m3u", "")
            plex_name = f"{emoji} {playlist_title}".strip() if emoji else playlist_title
            m3u_path = os.path.join(root, file)
            
            # --- SMART WIPE ---
            for pl in all_plex_playlists:
                if pl.title in [plex_name, playlist_title]:
                    if not pl.title.startswith(SYSTEM_EMOJI):
                        pl.delete()
                        break

            # --- MATCHING ---
            plex_tracks = []
            with open(m3u_path, 'r', encoding='utf-8-sig') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'): continue
                    
                    p_m3u = normalize_path(line)
                    p_translated = normalize_path(line.replace(MB_PREFIX, PLEX_PREFIX))
                    
                    if p_m3u in plex_map:
                        plex_tracks.append(plex_map[p_m3u])
                    elif p_translated in plex_map:
                        plex_tracks.append(plex_map[p_translated])

            # --- REBUILD ---
            if plex_tracks:
                plex.createPlaylist(plex_name, items=plex_tracks)
                art_status = "❌"
                
                # Check for Palette of BS override first, then fallback to standard search
                palette_art_path = os.path.join(ART_DIR, "Palette of BS.png")
                if folder_name == "Palette of BS" and os.path.exists(palette_art_path):
                    art = palette_art_path
                else:
                    art = find_art_file(playlist_title)

                if art:
                    time.sleep(1.5)
                    try:
                        plex.playlist(plex_name).uploadPoster(filepath=art)
                        art_status = "🎨"
                    except: pass
                
                print(f"✅ Created: {plex_name}")
                report.append([plex_name, len(plex_tracks), art_status])
            else:
                print(f"⚠️  No matches for: {playlist_title}")

    # --- FINAL SUMMARY ---
    print("\n" + "="*50)
    print(f"{'PLAYLIST':<35} | {'TRKS':<5} | {'ART'}")
    print("-" * 50)
    for row in report:
        print(f"{row[0]:<35} | {row[1]:<5} | {row[2]}")
    print("="*50)

if __name__ == "__main__":
    os.system('cls' if os.name == 'nt' else 'clear')
    sync_to_plex()
    print("\n✅ Sync Complete.")
    time.sleep(2)