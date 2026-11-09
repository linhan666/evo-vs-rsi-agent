#!/usr/bin/env python3
"""Read-only inventory of the phase-7 run tree. Prints one JSON blob.

Nothing here writes to the repository; it exists so the summary statistics can
be built on verified inputs instead of on the previous report's numbers.
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

ROOT = Path("/home/linhan_cluster/evo_vs_rsi")
RUNS = ROOT / "ops" / "phase7_runs"
PROTECTED = ROOT / "protected"
TARGET_ORDER = ["d2", "5ht", "adr", "drd2", "mor", "cbr", "kor", "ca2", "pt"]

out: dict = {"records": [], "receipts": [], "protected": {}, "runs_present": {}}

# ---------------------------------------------------------------- run records
pat = re.compile(r"^([ramw])_(\d\d)_([a-z0-9]+)(?:_(.+))?$")
for path in sorted(RUNS.glob("[ramw]_[0-9][0-9]_*.json")):
    m = pat.match(path.stem)
    if not m:
        continue
    rec = json.loads(path.read_text(encoding="utf-8"))
    arm, seq, target, label = m.group(1), int(m.group(2)), m.group(3), m.group(4) or ""
    row = {
        "file": path.name, "arm": arm, "seq": seq, "target": target, "label": label,
        "state": rec.get("state"), "wall": rec.get("wall_seconds"),
        "jobs": rec.get("jobs_total"), "failed": rec.get("jobs_failed"),
        "models": rec.get("models"), "best_model": rec.get("best_model"),
        "best_auroc": rec.get("best_scaffold_auroc", rec.get("auroc")),
        "best_ef": rec.get("best_scaffold_ef_at_1pct", rec.get("ef_at_1pct")),
        "tokens": (rec.get("tokens") or {}).get("total_tokens"),
        "calls": (rec.get("tokens") or {}).get("calls"),
        "locked_auroc": rec.get("locked_auroc"),
        "workdir": rec.get("workdir") or "",
        "recorded_at": rec.get("recorded_at"),
    }
    out["records"].append(row)
    out["runs_present"].setdefault(f"{arm}:{label or 'base'}", 0)
    out["runs_present"][f"{arm}:{label or 'base'}"] += 1

# ---------------------------------------------------------------- receipts
for row in out["records"]:
    wd = row["workdir"]
    if not wd or not Path(wd).is_dir():
        continue
    for p in sorted(Path(wd).rglob("*.json")):
        if ".jobs" in p.parts:
            continue
        try:
            payload = json.loads(p.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        if isinstance(payload, dict) and "metrics" in payload and "protected_output" in payload:
            out["receipts"].append({
                "arm": row["arm"], "target": row["target"], "label": row["label"],
                "seq": row["seq"], "evaluated_as": payload.get("target"),
                "desc_set": payload.get("desc_set"),
                "model": payload.get("model"),
                "auroc": (payload.get("metrics") or {}).get("auroc"),
                "auprc": (payload.get("metrics") or {}).get("auprc"),
                "ef1": (payload.get("metrics") or {}).get("ef_at_1pct"),
                "ef5": (payload.get("metrics") or {}).get("ef_at_5pct"),
                "file": str(p.relative_to(wd)),
            })

# ---------------------------------------------------------------- protected sets
for d in sorted(PROTECTED.glob("chembl37_ki_*")):
    for csv_path in sorted(d.glob("final_test_Ki.csv")):
        with csv_path.open(newline="", encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))
        if not rows:
            continue
        fields = {k.lower(): k for k in rows[0]}
        lab = fields.get("label")
        labels = [int(float(r[lab])) for r in rows if r.get(lab) not in (None, "")]
        n = len(labels)
        pos = sum(labels)
        prev = pos / n if n else None
        out["protected"][d.name] = {
            "n": n, "positives": pos, "prevalence": round(prev, 4) if prev else None,
            "ef1_max": round(1 / prev, 3) if prev else None,
            "top1pct_n": max(1, round(n * 0.01)),
        }

print(json.dumps(out, ensure_ascii=False, indent=1))
