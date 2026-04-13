from plexapi.server import PlexServer
import csv, os

PLEX_URL  = os.getenv("PLEX_URL")
PLEX_TOKEN = os.getenv("PLEX_TOKEN")

plex = PlexServer(PLEX_URL, PLEX_TOKEN)

songs = plex.library.section("Music").all()

with open("plex_music_export.csv", "w", newline='', encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["Artist", "Album", "Track", "Genre", "Year", "Duration_sec"])
    for s in songs:
        writer.writerow([
            s.artist(),
            s.album(),
            s.title,
            ", ".join(s.genres or []),
            s.year,
            round((s.duration or 0)/1000)
        ])
