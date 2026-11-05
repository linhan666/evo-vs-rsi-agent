#!/usr/bin/env python3
"""Repair the 007 module row whose inline code spans were eaten by a shell heredoc."""
import pathlib

row = pathlib.Path.home() / "evo_vs_rsi/docs/007-architecture.md"
text = row.read_text(encoding="utf-8")
broken = "the fixed argv a job runs;  backs logreg/rf/xgboost/catboost and  ranks an unlabeled library"
fixed = ("the fixed argv a job runs. `ml.train` backs logreg/rf/xgboost/catboost; "
         "`screening.rank` ranks an unlabeled library with a fitted model (predictions only)")
if broken in text:
    row.write_text(text.replace(broken, fixed, 1), encoding="utf-8")
    print("row repaired")
else:
    print("row already fine")
