===============================================================================
                       STARLIGHT MANOR TOOLBOX DOCUMENTATION
===============================================================================
Location: C:\Shortcut Hub\Toolbox
System environment: Windows / NAS / Python 3.10+
-------------------------------------------------------------------------------

[PEOPLE MANAGEMENT]
Tools for exporting and auditing person-based metadata.

  People-Export-GoogleContacts.py
    Connects to Google People API; exports names, birthdays, and contact info.
  
  People-Export-Immich.py
    Extracts person IDs and birthdates from the Immich API for audit.
  
  People-Export-DigiKamTags.py
    Queries local DigiKam SQLite DB to map face-tag hierarchies.

[PLEX & MUSIC]
Metadata auditing and collection/playlist automation.

  Plex-Export-MusicLibraryFull.py
    Master CSV export of every track (RatingKeys + absolute file paths).
  
  Plex-Export-AlbumMetadata.py
    Audits album-level tags (Genres, Styles, Moods, Labels).
  
  Plex-Update-CollectionsFromKeys.py
    Builds Plex Collections from RatingKey lists in "02 Drafts" folder.
  
  Plex-Query-QuickGenreCheck.py
    Direct SQLite query to verify genre tagging (e.g., Game Soundtracks).
  
  Plex-Sync-MusicBeePlaylists.py
    Syncs MusicBee .m3u files to Plex; handles NAS path translation.

[IMMICH AUTOMATION]
Metadata and organization enhancements for Immich.

  Immich-Update-RecentToAlbum.py
    Auto-groups assets uploaded in the last 12 hours into a target album.
  
  Immich-Update-TitlesFromFaces.py
    Sets asset titles to "Name (Age)" based on identified faces.
  
  Immich-Update-TitlesFaceSort.py
    Sets asset titles based on left-to-right visual order of faces.
	
DigiKam-Tag-to-Immich-Album.py 
	Syncs assets from DigiKam SQLite to Immich via tag-based routing logic

[MEDIA & ARCHIVE UTILITIES]
File system organization and bulk downloading.

  IA-Download-Batch.py
    Archive.org scraper with progress tracking and state-saving.
  
  IA-Update-FilenameCleanup.py
    Decodes URL characters (e.g., %20 to space) from IA downloads.
  
  Media-Update-OrganizeByAlbum.py
    Moves loose audio files into folders based on Album metadata tags.

[SYSTEM & BACKUP]
Core environment orchestration.

  Overnight_Robocopy_NAS_to_S.cmd
    Multi-threaded, additions-only sync from NAS to local S: drive.
    Flags: /E /FFT /XC /XN /XO /MT:16
  
  Launch Starlight Command Center.bat
    Starts local server shortcut and opens web UI (port 5270).

-------------------------------------------------------------------------------
Generated: 2026-03-02
===============================================================================