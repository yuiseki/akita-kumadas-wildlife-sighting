"""Check the Parquet against the CSV as served, with a second reader.

The CSV is read here with pyarrow's own CSV reader (all columns as strings), not with the csv
module of the export. Every row: same id, text columns equal (an empty 目撃時の状況 is null), the
time equals the string, the count and the coordinates equal, the point equals the coordinates. Also:
the row total equals the catalogue's datastore total, ids are unique, the file's sha256 equals the
manifest's.

    uv run python scripts/03_verify.py
"""

import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

import akita as a
import pyarrow.csv as pacsv
import pyarrow.parquet as pq
from shapely import from_wkb

ROOT = Path(__file__).parents[1]


def main() -> int:
    run = sorted((ROOT / "data" / "raw").glob("*/MANIFEST.json"))[-1].parent
    manifest = json.loads((run / "MANIFEST.json").read_text())
    path = run / "kumadas.csv"
    assert (
        hashlib.sha256(path.read_bytes()).hexdigest() == manifest["files"]["kumadas.csv"]["sha256"]
    )
    src = pacsv.read_csv(
        path,
        read_options=pacsv.ReadOptions(encoding="utf-8"),
        parse_options=pacsv.ParseOptions(newlines_in_values=True),
        convert_options=pacsv.ConvertOptions(
            column_types={c: "string" for c in a.COLUMNS}, strings_can_be_null=False
        ),
    ).to_pydict()
    t = pq.read_table(ROOT / "data" / "parquet" / "sighting.parquet")
    d = t.to_pydict()
    n = len(src["出没情報ID"])
    assert t.num_rows == n == manifest["datastore_total"], (t.num_rows, n)
    assert len(set(d["id"])) == n
    pairs = {
        "info_type": "情報種別", "municipality": "市町村", "address": "地番情報",
        "species": "獣種", "sex": "性別", "group": "単独か親子",
    }  # fmt: skip
    for i in range(n):
        assert d["id"][i] == int(src["出没情報ID"][i]), i
        for col, name in pairs.items():
            assert d[col][i] == src[name][i], (i, col)
        assert d["situation"][i] == (src["目撃時の状況"][i] or None), i
        assert d["observed_at"][i] == dt.datetime.strptime(src["目撃日時"][i], "%Y/%m/%d %H:%M"), i
        assert d["count"][i] == int(src["頭数"][i]), i
        assert d["latitude"][i] == float(src["x(緯度)"][i]) and d["longitude"][i] == float(
            src["y(経度)"][i]
        ), i
        g = from_wkb(d["geometry"][i])
        assert (g.x, g.y) == (d["longitude"][i], d["latitude"][i]), i
    geo = json.loads(t.schema.metadata[b"geo"])
    assert geo["columns"]["geometry"]["geometry_types"] == ["Point"]
    print(f"OK: {n} rows equal the CSV")
    return 0


if __name__ == "__main__":
    sys.exit(main())
