"""Shared helpers: the クマダス records of Akita Prefecture (CKAN open data catalogue) and how to read them."""

import csv
import datetime as dt
import io

CKAN = "https://ckan.pref.akita.lg.jp"
PACKAGE = "050008_shizenhogoka_003"
PACKAGE_URL = f"{CKAN}/dataset/{PACKAGE}"
API_PACKAGE = f"{CKAN}/api/3/action/package_show?id={PACKAGE}"
LICENSE_ID = "CC-BY-4.0"
COLUMNS = [
    "出没情報ID", "情報種別", "市町村", "地番情報", "目撃日時", "獣種", "性別",
    "単独か親子", "頭数", "目撃時の状況", "x(緯度)", "y(経度)",
]  # fmt: skip
INFO_TYPES = {"目撃", "痕跡(その他)", "痕跡(食害)", "人身被害"}
SPECIES = {"ツキノワグマ", "イノシシ", "ニホンジカ"}
SEX = {"不明", "メス", "オス"}
# Akita Prefecture, with a margin: every point of the source must fall in it
BBOX = (139.0, 38.5, 141.5, 40.9)  # lon min, lat min, lon max, lat max


def parse_time(s: str) -> dt.datetime:
    """`2026/9/30 22:03` (Japan time, no zone in the source)."""
    return dt.datetime.strptime(s, "%Y/%m/%d %H:%M")


def parse_csv(data: bytes) -> list[dict]:
    """The records as dicts of the source's own columns; refuses a header or a value it does not know."""
    rows = list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"), newline="")))
    if not rows:
        raise ValueError("no rows")
    if list(rows[0]) != COLUMNS:
        raise ValueError(f"unexpected header {list(rows[0])}")
    out = []
    for r in rows:
        if None in r or None in r.values():
            raise ValueError(f"ragged row {r.get('出没情報ID')}")
        if r["情報種別"] not in INFO_TYPES:
            raise ValueError(f"unknown 情報種別 {r['情報種別']!r}")
        if r["獣種"] not in SPECIES:
            raise ValueError(f"unknown 獣種 {r['獣種']!r}")
        if r["性別"] not in SEX:
            raise ValueError(f"unknown 性別 {r['性別']!r}")
        lat, lon = float(r["x(緯度)"]), float(r["y(経度)"])
        if not (BBOX[0] <= lon <= BBOX[2] and BBOX[1] <= lat <= BBOX[3]):
            raise ValueError(f"{r['出没情報ID']}: point outside Akita ({lat}, {lon})")
        out.append(
            {
                "id": int(r["出没情報ID"]),
                "info_type": r["情報種別"],
                "municipality": r["市町村"],
                "address": r["地番情報"],
                "observed_at": parse_time(r["目撃日時"]),
                "species": r["獣種"],
                "sex": r["性別"],
                "group": r["単独か親子"],
                "count": int(r["頭数"]),
                "situation": r["目撃時の状況"] or None,
                "latitude": lat,
                "longitude": lon,
            }
        )
    return out
