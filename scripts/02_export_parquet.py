"""Write GeoParquet of the クマダス records of Akita Prefecture.

One row per record of the source's CSV: id (出没情報ID), info_type (情報種別), municipality (市町村),
address (地番情報), observed_at (目撃日時, Japan time, no zone), species (獣種), sex (性別),
group (単独か親子), count (頭数), situation (目撃時の状況, null when empty; line breaks kept),
latitude (the source's `x(緯度)`), longitude (`y(経度)`), geometry (WKB Point). The source names the
latitude column x and the longitude column y; here they are named for what they hold. The source
states no datum; the points are written as WGS84 (EPSG:4326), the GeoParquet default.

    uv run python scripts/02_export_parquet.py [--version 2026-10-26]
"""

import argparse
import json
import sys
from pathlib import Path

import akita as a
import pyarrow as pa
import pyarrow.parquet as pq
from shapely.geometry import Point

ROOT = Path(__file__).parents[1]
SCHEMA = pa.schema(
    [
        ("id", pa.int32()),
        ("info_type", pa.string()),
        ("municipality", pa.string()),
        ("address", pa.string()),
        ("observed_at", pa.timestamp("s")),
        ("species", pa.string()),
        ("sex", pa.string()),
        ("group", pa.string()),
        ("count", pa.int16()),
        ("situation", pa.string()),
        ("latitude", pa.float64()),
        ("longitude", pa.float64()),
        ("geometry", pa.binary()),
    ]
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default=None)
    args = ap.parse_args()
    runs = sorted((ROOT / "data" / "raw").glob("*/MANIFEST.json"))
    raw = runs[-1].parent if args.version is None else ROOT / "data" / "raw" / args.version
    manifest = json.loads((raw / "MANIFEST.json").read_text())
    rows = a.parse_csv((raw / "kumadas.csv").read_bytes())
    if len(rows) != manifest["datastore_total"]:
        raise SystemExit(
            f"{len(rows)} rows, the catalogue's datastore says {manifest['datastore_total']}"
        )
    if len({r["id"] for r in rows}) != len(rows):
        raise SystemExit("出没情報ID is not unique")
    for r in rows:
        r["geometry"] = Point(r["longitude"], r["latitude"]).wkb
    geo = {
        "version": "1.1.0", "primary_column": "geometry",
        "columns": {"geometry": {"encoding": "WKB", "geometry_types": ["Point"]}},
    }  # fmt: skip
    t = pa.Table.from_pylist(rows, schema=SCHEMA).replace_schema_metadata(
        {b"geo": json.dumps(geo).encode()}
    )
    out = ROOT / "data" / "parquet"
    out.mkdir(parents=True, exist_ok=True)
    pq.write_table(t, out / "sighting.parquet", compression="zstd")
    (out / "columns.json").write_text(
        json.dumps({
            "run": raw.name, "rows": len(rows),
            "columns": {
                "id": "出没情報ID", "info_type": "情報種別", "municipality": "市町村",
                "address": "地番情報", "observed_at": "目撃日時 (Japan time, no zone)",
                "species": "獣種", "sex": "性別", "group": "単独か親子", "count": "頭数",
                "situation": "目撃時の状況 (null when empty)",
                "latitude": "x(緯度) of the source", "longitude": "y(経度) of the source",
                "geometry": "WKB Point (longitude, latitude), WGS84 assumed",
            },
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")  # fmt: skip
    print(len(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
