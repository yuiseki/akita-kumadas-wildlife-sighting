import datetime as dt

import akita as a
import pytest

HEAD = ",".join(a.COLUMNS)


def csv_of(*lines, head=HEAD):
    return ("﻿" + head + "\n" + "\n".join(lines) + "\n").encode()


ROW = '28054,目撃,秋田市,"〒010-0822 秋田県秋田市添川古城廻",2026/9/30 22:03,イノシシ,不明,単独,1,【投稿】,39.7572,140.1419'


def test_parse_row():
    r = a.parse_csv(csv_of(ROW))[0]
    assert r["id"] == 28054 and r["observed_at"] == dt.datetime(2026, 9, 30, 22, 3)
    assert r["situation"] == "【投稿】" and r["latitude"] == 39.7572 and r["longitude"] == 140.1419


def test_empty_situation_is_none_and_crlf_is_kept():
    r = a.parse_csv(csv_of(ROW.replace("【投稿】", "")))[0]
    assert r["situation"] is None
    r = a.parse_csv(csv_of(ROW.replace("【投稿】", '"a\r\nb"')))[0]
    assert r["situation"] == "a\r\nb"


@pytest.mark.parametrize(
    "bad",
    [
        ROW.replace("目撃,", "謎,", 1),
        ROW.replace("イノシシ", "タヌキ"),
        ROW.replace(",不明,", ",?,", 1),
        ROW.replace("39.7572,140.1419", "140.1419,39.7572"),  # latitude and longitude swapped
        ROW.replace("2026/9/30", "2026-9-30"),
    ],
)
def test_refuses_what_it_does_not_know(bad):
    with pytest.raises(ValueError):
        a.parse_csv(csv_of(bad))


def test_refuses_a_changed_header():
    with pytest.raises(ValueError):
        a.parse_csv(csv_of(ROW, head=HEAD + ",新しい列"))
