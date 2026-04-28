# module-grade-evaluator

A PySide6 desktop tool to track module grades and visualise where you stand.

## Features

- Editable tree of modules → tasks (name, credits, weight, score, target).
- Year average is credit-weighted across modules; module average is task-weighted.
- Four visualisations:
  1. **Modules vs targets** — bar chart with target markers and 1st / 2:1 / 2:2 / 3rd boundary lines.
  2. **Year breakdown** — credit-weighted donut with year average in the centre.
  3. **What do I need?** — for a target year %, the minimum score required on every remaining task, coloured green / amber / red by feasibility.
  4. **Sensitivity** — sliders for every unentered task; year average updates live.
- Auto-saves to `data/grades.json`. *Open* / *Save As* for named files.

## Run

```bash
python -m venv .venv
.venv\Scripts\activate           # Windows
# source .venv/bin/activate      # macOS/Linux
pip install -r requirements.txt
python main.py
```

## Tests

The pure scoring/required-score logic has no Qt dependency:

```bash
python tests/test_model.py
```

