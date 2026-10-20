import datetime as dt
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import focus_growth as F


def test_reads_page_data():
    blocks, weeks = F.load_data()
    assert blocks[0]["title"] == "Wake up & Morning Buffer" and blocks[0]["start"] == 450
    assert len(weeks) == 10 and all(len(w["days"]) == 6 for w in weeks)
    assert weeks[9]["title"] == "Execution & Certification"


def test_current_block_and_overnight():
    blocks, _ = F.load_data()
    assert F.current_block(blocks, 450) == 0  # 7:30 AM: wake up
    assert F.current_block(blocks, 300) == len(blocks) - 1  # 5 AM: still last night's sleep
    p = F.block_progress(blocks, 9 * 60 + 30)  # 9:30 AM, inside Job Applications (9:00–11:00)
    assert p["block"]["title"] == "Job Applications" and p["left"] == 90 and p["pct"] == 25


def test_time_format():
    assert F.hm(450) == "7:30 AM" and F.hm(780) == "1:00 PM" and F.hm(0) == "12:00 AM"


def test_sprint_weeks():
    start = dt.date(2026, 10, 12)
    assert F.sprint_week(start, dt.date(2026, 10, 11)) == 0
    assert F.sprint_week(start, dt.date(2026, 10, 12)) == 1
    assert F.sprint_week(start, dt.date(2026, 10, 20)) == 2
    assert F.week_dates(start, 2) == (dt.date(2026, 10, 19), dt.date(2026, 10, 24))


def test_exports(tmp_path):
    _, weeks = F.load_data()
    prog = F.Progress(tmp_path / "p.json")
    prog.start = dt.date(2026, 10, 12)
    for name, marker, count in (("s.md", "- [", 60), ("s.csv", "\n", 61), ("s.ics", "BEGIN:VEVENT", 60)):
        F.export(weeks, prog, tmp_path / name)
        assert (tmp_path / name).read_text().count(marker) == count
