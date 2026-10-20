"""focus_growth.py: the Python version of the Focus & Growth dashboard.

Same daily routine and 10-week study sprint as the web page (it reads both straight
from index.html, so editing the page updates the script too). Shows what you should
be doing right now, today's checklist and study task, and sprint progress. Progress is
saved to a small JSON file.

    python focus_growth.py                     # right now + today's checklist + today's study task
    python focus_growth.py routine             # the full daily timeline
    python focus_growth.py check 3             # tick routine block 3 for today (uncheck 3 to undo)
    python focus_growth.py start 2026-10-19    # set the sprint start date ("start today" also works)
    python focus_growth.py plan                # all 10 weeks with dates and progress
    python focus_growth.py week 4              # one week in detail
    python focus_growth.py done 4 Tue          # mark a sprint day complete (undone 4 Tue to undo)
    python focus_growth.py status              # sprint progress, current week, days left
    python focus_growth.py export plan.md      # the sprint as Markdown (or .csv, or .ics for your calendar)

Options: --progress FILE (default focus_growth_progress.json next to this script).
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
SPRINT_DAYS = 70  # 10 weeks; the page counts the sprint as ending 69 days after the start


# --------------------------------------------------------------------------- data from the page


def load_data(html_path: pathlib.Path = HERE / "index.html") -> tuple[list[dict], list[dict]]:
    """Return (routine blocks, sprint weeks) as defined in the web page."""
    text = html_path.read_text(encoding="utf-8")
    blocks_src = re.search(r"var BLOCKS=\[(.*?)\];", text, re.S).group(1)
    blocks = [{"start": int(s), "title": t, "note": n, "kind": k}
              for s, t, n, k in re.findall(r'\{s:(\d+),t:"([^"]*)",n:"([^"]*)",k:"([^"]*)"\}', blocks_src)]
    weeks = json.loads(re.search(r"var WEEKS=(\[.*?\]);\s*\n", text, re.S).group(1))
    weeks = [{"title": w["t"], "days": [{"day": d["n"], "task": d["x"]} for d in w["d"]]} for w in weeks]
    if not blocks or len(weeks) != 10:
        raise ValueError("could not read the routine and 10-week plan from index.html")
    return blocks, weeks


def hm(minutes: int) -> str:
    """Minutes after midnight → '7:30 AM'."""
    minutes %= 1440
    h, m = divmod(minutes, 60)
    return f"{h % 12 or 12}:{m:02d} {'PM' if h >= 12 else 'AM'}"


def current_block(blocks: list[dict], minute: int) -> int:
    """Index of the block in progress; before the first block you are still in last night's sleep."""
    if minute < blocks[0]["start"]:
        return len(blocks) - 1
    return max(i for i, b in enumerate(blocks) if minute >= b["start"])


def block_progress(blocks: list[dict], minute: int) -> dict:
    """Time left in the current block, % elapsed, and what comes next (same maths as the page)."""
    ci = current_block(blocks, minute)
    nxt = blocks[(ci + 1) % len(blocks)]
    start = blocks[ci]["start"]
    end = blocks[0]["start"] + 1440 if ci == len(blocks) - 1 else nxt["start"]
    m = minute + 1440 if (minute < blocks[0]["start"] and ci == len(blocks) - 1) else minute
    return {"index": ci, "block": blocks[ci], "next": nxt, "left": end - m,
            "pct": max(0.0, min(100.0, (m - start) / (end - start) * 100))}


def sprint_week(start: dt.date, today: dt.date | None = None) -> int:
    """Current sprint week (1-based); 0 before the sprint starts."""
    diff = ((today or dt.date.today()) - start).days
    return 0 if diff < 0 else diff // 7 + 1


def week_dates(start: dt.date, week: int) -> tuple[dt.date, dt.date]:
    a = start + dt.timedelta(days=(week - 1) * 7)
    return a, a + dt.timedelta(days=5)


def day_key(week: int, day_index: int) -> str:
    return f"w{week}d{day_index}"


# --------------------------------------------------------------------------- progress file


class Progress:
    def __init__(self, path: pathlib.Path):
        self.path = path
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        self.start: dt.date | None = dt.date.fromisoformat(data["start"]) if data.get("start") else None
        self.days: dict[str, bool] = data.get("days", {})
        self.routine: dict[str, list[int]] = data.get("routine", {})

    def ensure_start(self) -> dt.date:
        if not self.start:  # like the page: the first visit starts the sprint today
            self.start = dt.date.today()
            self.save()
        return self.start

    def save(self) -> None:
        self.path.write_text(json.dumps({"start": self.start.isoformat() if self.start else None,
                                         "days": {k: v for k, v in self.days.items() if v},
                                         "routine": self.routine}, indent=2), encoding="utf-8")


# --------------------------------------------------------------------------- views


def show_now(blocks, weeks, prog: Progress) -> None:
    now = dt.datetime.now()
    minute = now.hour * 60 + now.minute
    p = block_progress(blocks, minute)
    left = f"{p['left'] // 60} hr {p['left'] % 60} min" if p["left"] >= 60 else f"{p['left']} min"
    bar = "█" * round(p["pct"] / 5) + "░" * (20 - round(p["pct"] / 5))
    print(f"\n{now:%A, %B %d, %Y · %I:%M %p}")
    print(f"\nRight now: {p['block']['title']}")
    if p["block"]["note"]:
        print(f"  {p['block']['note']}")
    print(f"  {bar}  {left} left · next: {p['next']['title']} at {hm(p['next']['start'])}")
    show_routine(blocks, prog, compact=True)
    start = prog.ensure_start()
    w = sprint_week(start)
    wd = (dt.date.today() - start).days % 7  # day of the sprint week, as the page dates them
    print("\nToday's study task")
    if 1 <= w <= 10 and wd < 6:
        d = weeks[w - 1]["days"][wd]
        mark = "✓" if prog.days.get(day_key(w, wd)) else "○"
        print(f"  {mark} Week {w} · {weeks[w - 1]['title']} · {d['day']}: {d['task']}")
    elif 1 <= w <= 10:
        print("  Rest day: no sprint task today.")
    else:
        print("  Sprint not running today (see `status`).")
    print()


def show_routine(blocks, prog: Progress, compact: bool = False) -> None:
    now = dt.datetime.now()
    minute = now.hour * 60 + now.minute
    ci = current_block(blocks, minute)
    done = set(prog.routine.get(dt.date.today().isoformat(), []))
    print(f"\nToday's routine ({len(done)}/{len(blocks)} done)")
    for i, b in enumerate(blocks):
        flag = "  ← now" if i == ci else ""
        print(f"  [{'x' if i in done else ' '}] {i:>2}  {hm(b['start']):>8}  {b['title']}{flag}")
        if b["note"] and not compact:
            print(f"                     {b['note']}")


def show_week(weeks, prog: Progress, week: int) -> None:
    start = prog.ensure_start()
    a, b = week_dates(start, week)
    w = weeks[week - 1]
    done = sum(bool(prog.days.get(day_key(week, i))) for i in range(len(w["days"])))
    cw = sprint_week(start)
    tag = "  (this week)" if week == cw else "  (behind)" if 0 < week < cw and done < len(w["days"]) else ""
    print(f"\nWeek {week}: {w['title']}{tag}")
    print(f"  {a:%b %d} – {b:%b %d} · {done}/{len(w['days'])} days")
    for i, d in enumerate(w["days"]):
        print(f"    [{'x' if prog.days.get(day_key(week, i)) else ' '}] {d['day']}  {d['task']}")


def status(weeks, prog: Progress) -> None:
    start = prog.ensure_start()
    total = sum(len(w["days"]) for w in weeks)
    done = sum(1 for w_i, w in enumerate(weeks, 1) for d_i in range(len(w["days"])) if prog.days.get(day_key(w_i, d_i)))
    today = dt.date.today()
    end = start + dt.timedelta(days=SPRINT_DAYS - 1)
    left = (end - today).days
    cw = sprint_week(start)
    print(f"\nSprint started {start:%b %d, %Y} · {'not started yet' if cw == 0 else f'week {min(cw, 10)} of 10'}")
    pct = round(done / total * 100)
    print(f"  {'█' * (pct // 5)}{'░' * (20 - pct // 5)}  {done}/{total} sprint days complete ({pct}%)")
    print("  " + (f"Sprint ends in {left} days" if left > 0 else "Final day today" if left == 0 else f"Sprint ended {end:%b %d}"))
    behind = [i for i in range(1, min(cw, 11)) if i < cw and
              sum(bool(prog.days.get(day_key(i, d))) for d in range(6)) < 6]
    if behind:
        print(f"  Behind on week{'s' if len(behind) > 1 else ''}: {', '.join(map(str, behind))}")
    print()


def export(weeks, prog: Progress, out: pathlib.Path) -> None:
    start = prog.ensure_start()
    rows = []
    for wi, w in enumerate(weeks, 1):
        a, _ = week_dates(start, wi)
        for di, d in enumerate(w["days"]):
            rows.append((wi, w["title"], d["day"], a + dt.timedelta(days=di), d["task"], bool(prog.days.get(day_key(wi, di)))))
    ext = out.suffix.lower()
    if ext == ".csv":
        with out.open("w", newline="", encoding="utf-8") as f:
            c = csv.writer(f)
            c.writerow(["week", "theme", "day", "date", "task", "done"])
            for r in rows:
                c.writerow([r[0], r[1], r[2], r[3].isoformat(), r[4], "yes" if r[5] else ""])
    elif ext == ".ics":
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Growthhub//Focus & Growth//EN"]
        for r in rows:
            lines += ["BEGIN:VEVENT", f"UID:growthhub-w{r[0]}-{r[2]}-{start:%Y%m%d}@speedkelvyn.github.io", f"DTSTAMP:{stamp}",
                      f"DTSTART;VALUE=DATE:{r[3]:%Y%m%d}", f"DTEND;VALUE=DATE:{r[3] + dt.timedelta(days=1):%Y%m%d}",
                      f"SUMMARY:Week {r[0]} · {r[4].replace(',', chr(92) + ',')}", "END:VEVENT"]
        lines.append("END:VCALENDAR")
        out.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")
    else:
        md = [f"# 10-Week Sprint (starts {start:%b %d, %Y})", ""]
        for wi, w in enumerate(weeks, 1):
            a, b = week_dates(start, wi)
            md += [f"## Week {wi}: {w['title']} ({a:%b %d} – {b:%b %d})", ""]
            md += [f"- [{'x' if r[5] else ' '}] **{r[2]}** {r[4]}" for r in rows if r[0] == wi] + [""]
        out.write_text("\n".join(md), encoding="utf-8")
    print(f"Wrote {out}")


# --------------------------------------------------------------------------- CLI


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", nargs="?", default="now",
                    choices=["now", "routine", "check", "uncheck", "start", "plan", "week", "done", "undone", "status", "export"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--progress", type=pathlib.Path, default=HERE / "focus_growth_progress.json")
    a = ap.parse_args(argv)
    blocks, weeks = load_data()
    prog = Progress(a.progress)

    if a.command == "now":
        show_now(blocks, weeks, prog)
    elif a.command == "routine":
        show_routine(blocks, prog)
    elif a.command in ("check", "uncheck"):
        i = int(a.args[0])
        if not 0 <= i < len(blocks):
            raise SystemExit(f"block must be 0–{len(blocks) - 1}")
        key = dt.date.today().isoformat()
        done = set(prog.routine.get(key, []))
        (done.add if a.command == "check" else done.discard)(i)
        prog.routine[key] = sorted(done)
        prog.save()
        show_routine(blocks, prog, compact=True)
    elif a.command == "start":
        val = a.args[0] if a.args else "today"
        prog.start = dt.date.today() if val == "today" else dt.date.fromisoformat(val)
        prog.save()
        status(weeks, prog)
    elif a.command == "plan":
        for w in range(1, 11):
            show_week(weeks, prog, w)
        status(weeks, prog)
    elif a.command == "week":
        show_week(weeks, prog, max(1, min(10, int(a.args[0]) if a.args else sprint_week(prog.ensure_start()) or 1)))
    elif a.command in ("done", "undone"):
        if len(a.args) < 2 or a.args[1].title()[:3] not in DAY_NAMES:
            raise SystemExit("usage: done WEEK DAY   e.g. done 4 Tue")
        w, d = int(a.args[0]), DAY_NAMES.index(a.args[1].title()[:3])
        prog.ensure_start()
        prog.days[day_key(w, d)] = a.command == "done"
        prog.save()
        show_week(weeks, prog, w)
    elif a.command == "status":
        status(weeks, prog)
    elif a.command == "export":
        export(weeks, prog, pathlib.Path(a.args[0] if a.args else "sprint_plan.md"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
