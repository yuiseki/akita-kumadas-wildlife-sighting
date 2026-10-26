"""Download the クマダス records of Akita Prefecture from its CKAN open data catalogue.

Saves the dataset's metadata (package_show) and the CSV resource as served, with their sha256, the
Last-Modified and the row total that the catalogue's datastore states, in
data/raw/<version>/MANIFEST.json. Stops when the catalogue does not say CC-BY-4.0. The source
overwrites the file in place, so only the newest run is kept and published. The version is the UTC
date of the run.

    uv run python scripts/01_download.py [--version 2026-10-26]
"""

import argparse
import datetime as dt
import hashlib
import json
import sys
import time
import urllib.request
from pathlib import Path

import akita as a

ROOT = Path(__file__).parents[1]
UA = "akita-kumadas-wildlife-sighting/0.1 (+https://github.com/yuiseki/akita-kumadas-wildlife-sighting)"


def get(url: str) -> tuple[bytes, dict]:
    with urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": UA}), timeout=120
    ) as r:
        return r.read(), {h.lower(): v for h, v in r.headers.items()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default=dt.datetime.now(dt.UTC).strftime("%Y-%m-%d"))
    args = ap.parse_args()
    raw = ROOT / "data" / "raw" / args.version
    raw.mkdir(parents=True, exist_ok=True)
    body, _ = get(a.API_PACKAGE)
    pkg = json.loads(body)["result"]
    if pkg["license_id"] != a.LICENSE_ID:
        raise SystemExit(f"license_id is {pkg['license_id']!r}, not {a.LICENSE_ID}: stopping")
    (raw / "package.json").write_bytes(body)
    res = [r for r in pkg["resources"] if r["format"] == "CSV"]
    if len(res) != 1:
        raise SystemExit(f"expected one CSV resource, found {len(res)}")
    r = res[0]
    time.sleep(1)
    csv_body, h = get(r["url"])
    (raw / "kumadas.csv").write_bytes(csv_body)
    time.sleep(1)
    ds, _ = get(f"{a.CKAN}/api/3/action/datastore_search?resource_id={r['id']}&limit=0")
    manifest = {
        "retrieved": args.version,
        "page": a.PACKAGE_URL,
        "title": pkg["title"],
        "license_id": pkg["license_id"],
        "metadata_modified": pkg["metadata_modified"],
        "resource_last_modified": r["last_modified"],
        "datastore_total": json.loads(ds)["result"]["total"],
        "files": {
            "kumadas.csv": {
                "url": r["url"],
                "bytes": len(csv_body),
                "sha256": hashlib.sha256(csv_body).hexdigest(),
                "last_modified": h.get("last-modified"),
            },
            "package.json": {
                "url": a.API_PACKAGE,
                "bytes": len(body),
                "sha256": hashlib.sha256(body).hexdigest(),
            },
        },
    }
    (raw / "MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(pkg["title"], manifest["datastore_total"], len(csv_body))
    return 0


if __name__ == "__main__":
    sys.exit(main())
