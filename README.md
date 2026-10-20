# Focus & Growth

A personal dashboard that turns goals into a daily routine and a 10-week study sprint, covering Power BI (PL-300), SQL and analytics skills.

**Live app:** https://speedkelvyn.github.io/Growthhub/

## Features
- **Daily routine:** a timeline of the day with a checklist for today
- **10-week plan:** week-by-week milestones from a sprint start date you choose
- **Progress saved locally:** checklists persist in your browser

## Run it
Open `index.html` in any browser. No install or sign-up; data stays on your device (localStorage).

## Python version
`focus_growth.py` runs the same routine and sprint from the command line (it reads both from `index.html`):

```bash
python focus_growth.py                 # what to do right now, today's checklist and study task
python focus_growth.py check 2         # tick routine block 2 for today
python focus_growth.py done 4 Tue      # mark a sprint day complete
python focus_growth.py status          # progress, current week, days left
python focus_growth.py export plan.md  # sprint as Markdown (or .csv, .ics)
```

Standard library only. Tests: `python -m pytest tests`.

## Built with
HTML, CSS and vanilla JavaScript in a single file, hosted on GitHub Pages.
