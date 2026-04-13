#!/usr/bin/env python3
# album_to_folder_gui.py
#
# GUI-driven "Album → Folder" grouper with smart fallbacks:
# - Robust tag extraction across MP3/ID3, FLAC/Vorbis, MP4/M4A, OGG/OPUS, WMA/ASF, etc.
# - If Album tag is missing/blank, optionally uses the FILE'S PARENT FOLDER name.
# - Recursively scans audio files, creates album folders under the selected ROOT, and moves files.
# - Always shows dialogs (works fine when double-clicked without a console).
# - Writes a timestamped log next to the script.

import sys
import re
import shutil
import datetime
from pathlib import Path

# --- GUI helpers (tkinter) ---
import tkinter as tk
from tkinter import filedialog, messagebox

# --- Dependency check ---
try:
    from mutagen import File as MutagenFile
    from mutagen.id3 import ID3
    from mutagen.flac import FLAC
    from mutagen.oggvorbis import OggVorbis
    from mutagen.oggopus import OggOpus
    from mutagen.mp4 import MP4
    from mutagen.asf import ASF
    from mutagen.apev2 import APEv2
except ImportError:
    tk.Tk().withdraw()
    messagebox.showerror(
        "Missing Dependency",
        "This script requires the 'mutagen' package.\n\nInstall it with:\n\npip install mutagen"
    )
    sys.exit(1)

# --- Config ---
AUDIO_EXTS = {
    ".mp3", ".flac", ".m4a", ".mp4", ".aac", ".ogg", ".oga", ".opus", ".wma", ".wav", ".aiff", ".aif"
}
INVALID_WIN_PATTERN = re.compile(r'[<>:"/\\|?*]')
RESERVED = {
    "CON","PRN","AUX","NUL",
    "COM1","COM2","COM3","COM4","COM5","COM6","COM7","COM8","COM9",
    "LPT1","LPT2","LPT3","LPT4","LPT5","LPT6","LPT7","LPT8","LPT9"
}

# --- Logging ---
def get_log_path(script_path: Path) -> Path:
    ts = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    return script_path.with_name(f"{script_path.stem}_{ts}.log")

class Logger:
    def __init__(self, logfile: Path):
        self.logfile = logfile
        try:
            self.fp = open(logfile, "a", encoding="utf-8", errors="ignore")
        except Exception:
            self.fp = None

    def write(self, msg: str):
        line = msg if msg.endswith("\n") else msg + "\n"
        if self.fp:
            try:
                self.fp.write(line)
                self.fp.flush()
            except Exception:
                pass

    def close(self):
        if self.fp:
            try:
                self.fp.close()
            except Exception:
                pass

# --- Helpers ---
def sanitize_for_windows(name: str, replacement: str = "_") -> str:
    if not name or not name.strip():
        return "Unknown Album"
    cleaned = INVALID_WIN_PATTERN.sub(replacement, name).strip().rstrip(".")
    if cleaned.upper() in RESERVED:
        cleaned = cleaned + "_"
    return cleaned or "Unknown Album"

def ensure_unique_path(dest_path: Path) -> Path:
    if not dest_path.exists():
        return dest_path
    stem, suffix, parent = dest_path.stem, dest_path.suffix, dest_path.parent
    i = 1
    while True:
        candidate = parent / f"{stem} ({i}){suffix}"
        if not candidate.exists():
            return candidate
        i += 1

def gather_files(root: Path) -> list[Path]:
    return [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in AUDIO_EXTS]

# --- Tag reading (robust across containers) ---
def _first_str(val):
    """Return the first non-empty string from a value or list/tuple of values."""
    if val is None:
        return None
    if isinstance(val, (list, tuple)):
        for v in val:
            s = str(v).strip()
            if s:
                return s
        return None
    s = str(val).strip()
    return s or None

def _get_ci(d, keys):
    """
    Case-insensitive getter for dict-like tag stores.
    Tries each key variant (original, lower, upper) and returns first match value.
    """
    if not hasattr(d, "keys"):
        return None
    existing = {str(k).lower(): k for k in d.keys()}
    for k in keys:
        k_lower = k.lower()
        if k_lower in existing:
            return d.get(existing[k_lower])
    return None

def read_album_and_artist(path: Path, log: Logger | None = None) -> tuple[str | None, str | None, str | None]:
    """
    Return (album, albumartist, artist) using container-specific strategies.
    - FLAC / OGG / OPUS: Vorbis-style comments; keys vary, case-insensitive.
    - MP4/M4A: uses MP4 atoms (©alb, aART, ©ART).
    - MP3: Easy tags may not be reliable; use ID3 frames for fallback.
    - WMA/ASF: WM/AlbumTitle, WM/AlbumArtist, Author.
    - APE/WAV: best-effort common keys.
    """
    audio = MutagenFile(str(path))
    if audio is None:
        return None, None, None

    album = albumartist = artist = None

    try:
        # --- FLAC / OGG VORBIS / OPUS ---
        if isinstance(audio, (FLAC, OggVorbis, OggOpus)):
            # Common variants seen in the wild
            album_keys = ["ALBUM"]
            albumartist_keys = ["ALBUMARTIST", "ALBUM ARTIST", "BAND"]
            artist_keys = ["ARTIST"]

            if hasattr(audio, "tags") and audio.tags is not None:
                album = _first_str(_get_ci(audio.tags, album_keys))
                albumartist = _first_str(_get_ci(audio.tags, albumartist_keys))
                artist = _first_str(_get_ci(audio.tags, artist_keys))

        # --- MP4 / M4A ---
        elif isinstance(audio, MP4):
            # Atoms: ©alb (album), aART (album artist), ©ART (artist)
            album = _first_str(audio.tags.get("\xa9alb")) if audio.tags else None
            albumartist = _first_str(audio.tags.get("aART")) if audio.tags else None
            artist = _first_str(audio.tags.get("\xa9ART")) if audio.tags else None

        # --- WMA / ASF ---
        elif isinstance(audio, ASF):
            # WM/AlbumTitle, WM/AlbumArtist, Author
            if audio.tags:
                album = _first_str(audio.tags.get("WM/AlbumTitle"))
                albumartist = _first_str(audio.tags.get("WM/AlbumArtist"))
                artist = _first_str(audio.tags.get("Author"))

        # --- APE (Monkey's, MPC, etc.) ---
        elif isinstance(audio.tags, APEv2):
            # typical keys: ALBUM, ALBUMARTIST, ARTIST
            album = _first_str(_get_ci(audio.tags, ["ALBUM"]))
            albumartist = _first_str(_get_ci(audio.tags, ["ALBUMARTIST", "ALBUM ARTIST", "BAND"]))
            artist = _first_str(_get_ci(audio.tags, ["ARTIST"]))

        # --- Generic / MP3 fallback ---
        else:
            # Try generic dict-like tags first
            t = audio.tags if getattr(audio, "tags", None) else {}
            if t:
                album = _first_str(_get_ci(t, ["album", "ALBUM", "TALB"]))
                albumartist = _first_str(_get_ci(t, ["albumartist", "ALBUMARTIST", "TPE2", "BAND"]))
                artist = _first_str(_get_ci(t, ["artist", "ARTIST", "TPE1"]))

        # MP3 specific: direct ID3 read if album missing
        if (album is None or not album.strip()) and path.suffix.lower() == ".mp3":
            try:
                id3 = ID3(str(path))
                frame = id3.get("TALB")
                if frame and frame.text:
                    album = _first_str(frame.text)
                if (albumartist is None or not albumartist.strip()):
                    # Band/Orchestra/Accompaniment (often used as Album Artist)
                    tpe2 = id3.get("TPE2")
                    if tpe2 and tpe2.text:
                        albumartist = _first_str(tpe2.text)
                if (artist is None or not artist.strip()):
                    tpe1 = id3.get("TPE1")
                    if tpe1 and tpe1.text:
                        artist = _first_str(tpe1.text)
            except Exception:
                pass

    except Exception as e:
        if log:
            log.write(f"[DEBUG] Tag read error for {path}: {e}")

    # Normalize empties to None
    album = album.strip() if album else None
    albumartist = albumartist.strip() if albumartist else None
    artist = artist.strip() if artist else None

    # If albumartist missing, use artist
    if not albumartist and artist:
        albumartist = artist

    # Light debug for missing album on known-tag types
    if (album is None) and log:
        log.write(f"[DEBUG] No ALBUM tag found: {path}")

    return album, albumartist, artist

def resolve_album_and_artist(path: Path, log: Logger | None = None) -> tuple[str, str | None]:
    album, albumartist, artist = read_album_and_artist(path, log=log)
    # albumartist already normalized in read_album_and_artist
    return (album or ""), (albumartist or None)

# --- Main ---
def main():
    gui = tk.Tk()
    gui.withdraw()

    # Pick root folder
    root_str = filedialog.askdirectory(title="Select ROOT folder containing your music")
    if not root_str:
        messagebox.showinfo("Album to Folder", "Cancelled (no folder selected).")
        return
    root = Path(root_str)
    if not root.exists() or not root.is_dir():
        messagebox.showerror("Album to Folder", f"'{root}' is not a valid folder.")
        return

    # Option: include artist in folder name?
    include_artist = messagebox.askyesno(
        "Folder Naming",
        "Use 'Album Artist - Album' as the folder name when Album Artist is available?\n\nYes = 'Artist - Album'\nNo = 'Album'"
    )

    # Option: fallback to parent folder name if album tag is missing
    fallback_to_parent = messagebox.askyesno(
        "Missing Album Tag",
        "If a file has no Album tag, use its PARENT FOLDER name instead?\n\nRecommended: Yes"
    )

    # Prepare logging
    script_path = Path(sys.argv[0]).resolve()
    log_path = get_log_path(script_path)
    log = Logger(log_path)

    try:
        files = gather_files(root)
        if not files:
            messagebox.showinfo("Album to Folder", f"No audio files found under:\n{root}\n\nLog: {log_path}")
            return

        total = len(files)
        moved = 0
        skipped = 0
        errors = 0

        log.write(f"ROOT: {root}")
        log.write(f"Include Artist: {'YES' if include_artist else 'NO'}")
        log.write(f"Fallback to Parent: {'YES' if fallback_to_parent else 'NO'}")
        log.write(f"Files found: {total}")
        log.write("-" * 72)

        if not messagebox.askyesno(
            "Confirm",
            f"Found {total} audio file(s) under:\n{root}\n\nProceed to group by album and move them?"
        ):
            messagebox.showinfo("Album to Folder", f"Operation cancelled.\n\nLog: {log_path}")
            return

        for idx, src in enumerate(files, start=1):
            try:
                album, album_artist = resolve_album_and_artist(src, log=log)

                # Fallback to parent folder name if Album tag is missing/blank
                if not album and fallback_to_parent:
                    album = src.parent.name

                # Final normalization
                album = album if album else "Unknown Album"
                folder_name = f"{album_artist} - {album}" if (include_artist and album_artist) else album
                folder_name = sanitize_for_windows(folder_name)

                dest_folder = root / folder_name

                # Skip if already in the correct folder directly under root
                try:
                    rel = src.relative_to(root)
                    if rel.parent == Path(folder_name):
                        log.write(f"[{idx}/{total}] SKIP (already grouped): {src}")
                        skipped += 1
                        continue
                except Exception:
                    pass

                dest_folder.mkdir(parents=True, exist_ok=True)
                dest_file = ensure_unique_path(dest_folder / src.name)
                shutil.move(str(src), str(dest_file))
                log.write(f"[{idx}/{total}] MOVE: {src}  -->  {dest_file}")
                moved += 1

            except Exception as e:
                log.write(f"[{idx}/{total}] ERROR: {src} :: {e}")
                errors += 1

        summary = (
            f"Album to Folder — Complete\n\n"
            f"Root: {root}\n"
            f"Total files scanned : {total}\n"
            f"Moved               : {moved}\n"
            f"Skipped             : {skipped}\n"
            f"Errors              : {errors}\n\n"
            f"Log saved to:\n{log_path}"
        )
        messagebox.showinfo("Album to Folder", summary)

    except Exception as e:
        messagebox.showerror("Album to Folder", f"Unexpected error:\n{e}\n\nLog (if created): {log_path}")
    finally:
        log.close()

if __name__ == "__main__":
    main()
