import sys
import math
import json
import requests
from datetime import datetime, timedelta, timezone

# ================= CONFIG =================
IMMICH_BASE_URL = "http://192.168.68.163:2283"
IMMICH_API_KEY = "vzMRFhzZPeC74FJ6ZMyFT4aOV1t2P7BWKTsKwc37A"
HOURS_BACK = 12
PAGE_SIZE = 1000  # max allowed by API docs for searchAssets
# ==========================================

API_PREFIX = "/api"
HEADERS_JSON = {
    "x-api-key": IMMICH_API_KEY,  # auth header per Immich API docs
    "Accept": "application/json",
    "Content-Type": "application/json",
}

def iso_utc(dt: datetime) -> str:
    # Immich expects date-time strings; use UTC ISO8601 with 'Z'
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

def http_raise(resp: requests.Response, context: str) -> None:
    if resp.status_code >= 400:
        try:
            body = resp.json()
        except Exception:
            body = resp.text
        raise RuntimeError(f"{context} failed: HTTP {resp.status_code}\n{body}")

def get_recent_asset_ids(hours_back: int) -> list[str]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)
    cutoff_iso = iso_utc(cutoff)

    url = f"{IMMICH_BASE_URL}{API_PREFIX}/search/metadata"
    page = 1
    asset_ids: list[str] = []

    while True:
        payload = {
            "createdAfter": cutoff_iso,
            "page": page,
            "size": PAGE_SIZE,
            "order": "desc",
            # Optional filters if you want later:
            # "type": "IMAGE",
            # "withDeleted": False,
        }

        resp = requests.post(url, headers=HEADERS_JSON, data=json.dumps(payload), timeout=60)
        http_raise(resp, "Search assets (metadata)")

        data = resp.json()

        # Immich responses vary a bit by version/docs site.
        # Try the common shapes:
        items = []
        if isinstance(data, dict):
            if "assets" in data and isinstance(data["assets"], dict):
                items = data["assets"].get("items") or []
            elif "items" in data:
                items = data.get("items") or []
        if not items:
            break

        # Each item is an asset object; id is the asset UUID/string
        for a in items:
            if isinstance(a, dict) and a.get("id"):
                asset_ids.append(a["id"])

        # Stop if fewer than a full page returned (or no next page marker)
        if len(items) < PAGE_SIZE:
            break

        page += 1

    # De-dup while preserving order
    seen = set()
    deduped = []
    for aid in asset_ids:
        if aid not in seen:
            seen.add(aid)
            deduped.append(aid)

    return deduped

def list_albums() -> list[dict]:
    url = f"{IMMICH_BASE_URL}{API_PREFIX}/albums"
    resp = requests.get(url, headers={"x-api-key": IMMICH_API_KEY, "Accept": "application/json"}, timeout=60)
    http_raise(resp, "List albums")
    albums = resp.json()
    if not isinstance(albums, list):
        raise RuntimeError(f"Unexpected albums response shape: {albums}")
    return albums

def choose_album(albums: list[dict]) -> dict:
    # Sort by albumName for easier selection
    albums_sorted = sorted(albums, key=lambda a: (a.get("albumName") or "").lower())

    print("\nAvailable albums:")
    for idx, a in enumerate(albums_sorted, start=1):
        name = a.get("albumName", "<no name>")
        aid = a.get("id", "<no id>")
        asset_count = a.get("assetCount", "?")
        print(f"  {idx:>3}. {name}  (assets: {asset_count})  [{aid}]")

    while True:
        raw = input("\nPick an album by number (or type part of the album name): ").strip()
        if not raw:
            continue

        # number selection
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(albums_sorted):
                return albums_sorted[n - 1]
            print("Invalid number.")
            continue

        # substring match
        matches = [a for a in albums_sorted if raw.lower() in (a.get("albumName") or "").lower()]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            print(f"Matched {len(matches)} albums. Please be more specific or use the number.")
            for a in matches[:15]:
                print(f"  - {a.get('albumName')} [{a.get('id')}]")
            continue

        print("No matches. Try again.")

def add_assets_to_album(album_id: str, asset_ids: list[str]) -> None:
    if not asset_ids:
        print("No assets to add.")
        return

    url = f"{IMMICH_BASE_URL}{API_PREFIX}/albums/{album_id}/assets"

    # Chunk to avoid oversized requests
    CHUNK = 1000
    total = len(asset_ids)
    chunks = math.ceil(total / CHUNK)

    added_ok = 0
    non_duplicate_errors = []

    for i in range(chunks):
        chunk_ids = asset_ids[i * CHUNK : (i + 1) * CHUNK]
        payload = {"ids": chunk_ids}

        resp = requests.put(url, headers=HEADERS_JSON, data=json.dumps(payload), timeout=60)
        http_raise(resp, "Add assets to album")

        results = resp.json()
        # results is typically a list of {id, success, error?}
        if isinstance(results, list):
            for r in results:
                if r.get("success") is True:
                    added_ok += 1
                else:
                    # duplicate is common/benign; keep track but don’t fail
                    err = r.get("error") or "unknown"
                    if err != "duplicate":
                        non_duplicate_errors.append(r)

        print(f"Chunk {i+1}/{chunks}: processed {len(chunk_ids)}")

    print(f"\nDone. Successfully added: {added_ok}/{total}")
    if non_duplicate_errors:
        print("\nNon-duplicate errors (first 25 shown):")
        for r in non_duplicate_errors[:25]:
            print(f"  - id={r.get('id')} error={r.get('error')}")

def main() -> int:
    print(f"Searching for assets uploaded in the last {HOURS_BACK} hours...")
    asset_ids = get_recent_asset_ids(HOURS_BACK)

    print(f"\nFound {len(asset_ids)} assets.")
    if asset_ids:
        print("\nAsset IDs:")
        for aid in asset_ids:
            print(aid)

    if not asset_ids:
        print("\nNothing to add. Exiting.")
        return 0

    albums = list_albums()
    if not albums:
        print("\nNo albums found in this account. Exiting.")
        return 1

    album = choose_album(albums)
    album_name = album.get("albumName", "<no name>")
    album_id = album.get("id")
    if not album_id:
        print("Selected album has no id. Exiting.")
        return 1

    confirm = input(f"\nAdd {len(asset_ids)} assets to album '{album_name}'? (y/n): ").strip().lower()
    if confirm != "y":
        print("Cancelled.")
        return 0

    add_assets_to_album(album_id, asset_ids)
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nCancelled.")
        raise
    except Exception as e:
        print(f"\nERROR: {e}")
        raise
