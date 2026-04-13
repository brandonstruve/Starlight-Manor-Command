import re
import sys
import requests
from datetime import datetime

# ================= CONFIG =================
IMMICH_BASE_URL = "http://192.168.68.163:2283"
IMMICH_API_KEY = "vzMRFhzZPeC74FJ6ZMyFT4aOV1t2P7BWKTsKwc37A"
# ==========================================

UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)

SESSION = requests.Session()
SESSION.headers.update({
    "x-api-key": IMMICH_API_KEY,
    "Accept": "application/json",
    "Content-Type": "application/json",
})


def extract_uuid(text: str) -> str:
    m = UUID_RE.search(text)
    if not m:
        raise ValueError("No UUID found in input")
    return m.group(0)


def iso_to_date(s: str | None):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def compute_age(birth: str, on_date):
    try:
        b = datetime.strptime(birth, "%Y-%m-%d").date()
    except ValueError:
        return None
    years = on_date.year - b.year
    if (on_date.month, on_date.day) < (b.month, b.day):
        years -= 1
    return years


def get_asset(asset_id: str):
    url = f"{IMMICH_BASE_URL}/api/assets/{asset_id}"
    r = SESSION.get(url, timeout=30)
    r.raise_for_status()
    return r.json()


def get_album_assets(album_id: str):
    url = f"{IMMICH_BASE_URL}/api/albums/{album_id}"
    r = SESSION.get(url, timeout=30)
    r.raise_for_status()
    data = r.json()
    return data.get("assets", [])


def update_asset_title(asset_id: str, title: str):
    url = f"{IMMICH_BASE_URL}/api/assets"
    body = {
        "ids": [asset_id],
        "description": title
    }
    r = SESSION.put(url, json=body, timeout=30)
    r.raise_for_status()


def build_title(asset: dict) -> str | None:
    people = asset.get("people") or []
    if not people:
        return None

    photo_date = (
        iso_to_date(asset.get("localDateTime"))
        or iso_to_date(asset.get("fileCreatedAt"))
        or iso_to_date(asset.get("createdAt"))
    )

    parts = []
    for p in people:
        name = p.get("name")
        birth = p.get("birthDate")
        if not name:
            continue

        if photo_date and birth:
            age = compute_age(birth, photo_date)
            if age is not None:
                parts.append(f"{name} ({age})")
                continue

        parts.append(name)

    return ", ".join(dict.fromkeys(parts)) or None


def process_asset(asset_id: str):
    asset = get_asset(asset_id)
    title = build_title(asset)

    if not title:
        print(f"⏭️  {asset_id} — no usable people data")
        return

    update_asset_title(asset_id, title)
    print(f"✅ {asset_id}")
    print(f"   Title set to: {title}")


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  py immich_set_title_from_people.py <photo-url | album-url>")
        sys.exit(1)

    input_value = sys.argv[1]
    uuid = extract_uuid(input_value)

    if "/albums/" in input_value:
        print("📁 Album detected")
        assets = get_album_assets(uuid)
        print(f"Found {len(assets)} assets\n")

        for a in assets:
            process_asset(a["id"])
    else:
        print("🖼️  Single photo detected\n")
        process_asset(uuid)


if __name__ == "__main__":
    main()
