"""Write data/README.md (the dataset card), data/LICENSE and data/provenance.yaml.

uv run python scripts/04_card.py
"""

import json
import sys
from collections import Counter
from pathlib import Path

import akita as a
import pyarrow.parquet as pq

ROOT = Path(__file__).parents[1]
REPO = "akita-kumadas-wildlife-sighting"

CARD = """---
license: cc-by-4.0
license_name: cc-by-4.0
license_link: https://creativecommons.org/licenses/by/4.0/legalcode.ja
language:
- ja
tags:
- japan
- akita
- bear
- wildlife
- geospatial
size_categories:
- 10K<n<100K
pretty_name: Wildlife sightings of Akita Prefecture (クマダス)
---

# {repo}

The sighting records of Akita Prefecture's マップシステム『クマダス』 (Asiatic black bear,
wild boar and sika deer: sightings, traces and injuries to people): {rows:,} records from
{first} to {last}, each with the place (address text and latitude and longitude), the time, the
species, the group and the number of animals. As GeoParquet, with the CSV as served.

## Source

- Catalogue entry: <{page}> (秋田県オープンデータカタログ, 自然保護課), titled
  「{title}」. The catalogue states the licence `{license_id}`, the update frequency
  「毎月」 (monthly), metadata last modified {meta_modified} and the file last modified
  {res_modified}. The record total in the catalogue's datastore, {total:,}, equals the rows here.
- File: `kumadas.csv` as served (UTF-8 with a byte order mark; {csv_bytes:,} bytes), kept unchanged
  under `raw/{run}/` with its sha256 in `MANIFEST.json`, with the catalogue's `package.json`.
  Fetched {fetched}. The source overwrites the file each month, so this repository holds the
  state of {fetched} only.

## Files

| Path | Content |
|---|---|
| `parquet/sighting.parquet` | all {rows:,} records |
| `parquet/columns.json` | the column list |
| `raw/{run}/kumadas.csv` | the CSV as served |

## Columns

| Column | Source column | Content |
|---|---|---|
| `id` | 出没情報ID | integer, unique |
| `info_type` | 情報種別 | {info_types} |
| `municipality` | 市町村 | one of {n_muni} municipalities of Akita |
| `address` | 地番情報 | postal code and address text of the place |
| `observed_at` | 目撃日時 | timestamp in Japan time, no time zone |
| `species` | 獣種 | {species} |
| `sex` | 性別 | 不明, メス, オス |
| `group` | 単独か親子 | 単独, 親子（ツキノワグマ）, 群れ（イノシシ、二ホンジカ） as written |
| `count` | 頭数 | number of animals (an integer; {zero:,} records say 0) |
| `situation` | 目撃時の状況 | free text, null when empty ({empty:,} records); line breaks are kept |
| `latitude`, `longitude` | `x(緯度)`, `y(経度)` | the source names the latitude column x and the longitude column y; here they are named for what they hold |
| `geometry` | | the point as WKB (longitude, latitude), WGS84 assumed |

## What was changed

- Column names (above) and types: `observed_at` is parsed from `2026/9/30 22:03`; `count` is an
  integer; an empty 目撃時の状況 is null. The values are otherwise as in the source (the Parquet was
  checked against the CSV with a second CSV reader, every row: text, time, number and coordinates
  equal).
- The source states no datum for the coordinates. They are written as they are, and the GeoParquet
  metadata carries no crs, which means the default, WGS84 (OGC:CRS84). All points fall inside
  Akita Prefecture's bounding box (checked).
- Nothing was removed, merged or corrected.

## Counts

| Species | Records |
|---|---|
{species_rows}

| Information type | Records |
|---|---|
{type_rows}

| Year (by 目撃日時) | ツキノワグマ | イノシシ | ニホンジカ |
|---|---|---|---|
{year_rows}

## Known issues

- Three species are mixed in one table; filter on `species` for bears.
- {posted:,} records have the 目撃時の状況 「【投稿】」, which the catalogue does not explain; it seems
  to mark reports posted by the public (the page of the system itself was not read).
  They are in the licence the catalogue gives the whole file; the source does not say who posted them.
- 出没情報ID runs from {id_min} to {id_max} but there are {rows:,} records: {id_gaps:,} IDs are not in
  the file (deleted or never published; the source does not say).
- The place is an address or a landmark, as the reporter gave it, and the point comes with it; the
  accuracy of a point is not stated by the source. The records are reports: one animal can be
  reported many times, and the counts are not a census.
- A monthly overwrite: past states are not kept here; the date of the state is in the title of the
  catalogue entry and in the manifest.

## Licence

The catalogue states Creative Commons Attribution 4.0 (`CC-BY-4.0`) for the entry. This dataset is
offered under CC BY 4.0 and the credit is to Akita Prefecture:

> 出典：秋田県「ツキノワグマ等情報マップシステム『クマダス』データ」（{page}）を加工して作成
"""


def main() -> int:
    run = sorted((ROOT / "data" / "raw").glob("*/MANIFEST.json"))[-1].parent
    m = json.loads((run / "MANIFEST.json").read_text())
    cols = json.loads((ROOT / "data/parquet/columns.json").read_text())
    assert cols["run"] == run.name
    d = pq.read_table(ROOT / "data/parquet/sighting.parquet").drop(["geometry"]).to_pydict()
    n = cols["rows"]
    sp = Counter(d["species"])
    ty = Counter(d["info_type"])
    yr = Counter((t.year, s) for t, s in zip(d["observed_at"], d["species"], strict=True))
    years = sorted({y for y, _ in yr})
    ids = d["id"]
    card = CARD.format(
        repo=REPO, rows=n, page=a.PACKAGE_URL, title=m["title"], license_id=m["license_id"],
        meta_modified=m["metadata_modified"][:10], res_modified=m["resource_last_modified"][:10],
        total=m["datastore_total"], csv_bytes=m["files"]["kumadas.csv"]["bytes"], run=run.name,
        fetched=run.name, first=min(d["observed_at"]).date(), last=max(d["observed_at"]).date(),
        info_types=", ".join(f"`{k}`" for k in sorted(a.INFO_TYPES)), n_muni=len(set(d["municipality"])),
        species=", ".join(sorted(a.SPECIES)), zero=sum(c == 0 for c in d["count"]),
        empty=sum(s is None for s in d["situation"]),
        species_rows="\n".join(f"| {k} | {v:,} |" for k, v in sp.most_common()),
        type_rows="\n".join(f"| {k} | {v:,} |" for k, v in ty.most_common()),
        year_rows="\n".join(
            f"| {y} | {yr[(y, 'ツキノワグマ')]:,} | {yr[(y, 'イノシシ')]:,} | {yr[(y, 'ニホンジカ')]:,} |" for y in years
        ),
        posted=sum(s == "【投稿】" for s in d["situation"]), id_min=min(ids), id_max=max(ids),
        id_gaps=max(ids) - min(ids) + 1 - n,
    )  # fmt: skip
    data = ROOT / "data"
    (data / "README.md").write_text(card, encoding="utf-8")
    (data / "LICENSE").write_text(
        "CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/legalcode)\n\n"
        "The records are from 秋田県 ツキノワグマ等情報マップシステム『クマダス』データ, published in the\n"
        f"prefecture's open data catalogue under CC BY 4.0 ({a.PACKAGE_URL}), processed as described in README.md.\n"
        f"Credit: 出典：秋田県「ツキノワグマ等情報マップシステム『クマダス』データ」（{a.PACKAGE_URL}）を加工して作成\n",
        encoding="utf-8",
    )
    (data / "provenance.yaml").write_text(
        f"source: 秋田県 ツキノワグマ等情報マップシステム『クマダス』データ\nurl: {a.PACKAGE_URL}\n"
        f"license: {m['license_id']}\nrun: {run.name}\nretrieved: {run.name}\n"
        f"metadata_modified: {m['metadata_modified']}\nresource_last_modified: {m['resource_last_modified']}\n"
        f"rows: {n}\ncsv_sha256: {m['files']['kumadas.csv']['sha256']}\n",
        encoding="utf-8",
    )
    print("wrote data/README.md, LICENSE, provenance.yaml")
    return 0


if __name__ == "__main__":
    sys.exit(main())
