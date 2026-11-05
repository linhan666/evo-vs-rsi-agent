#!/usr/bin/env python3
"""Record the three dual-endpoint agreement results into the experience store."""
import os
import subprocess

ROOT = os.path.expanduser("~/evo_vs_rsi")
STORE = ROOT + "/scientific/.artifacts/experience/experience.json"
DUAL = ROOT + "/scientific/.artifacts/dual"
PYBIN = ROOT + "/scientific/.venv/bin/python"

NOTES = {
    "MOR": ("Ki vs IC50 ranks on same 100k library: Spearman 0.054 - near-random, top100 overlap 2/100. "
            "The two channel views diverge almost completely for MOR; dual-channel union screening is justified, "
            "single-channel shortlists are endpoint-specific."),
    "KOR": ("Ki vs IC50 ranks: Spearman 0.4103, top100 overlap 0/100. Weak rank concordance but disjoint "
            "shortlists; treat Ki and IC50 top-lists as complementary."),
    "DRD2": ("Ki vs IC50 ranks: Spearman 0.276, top100 overlap 0/100. Same complementary-shortlist conclusion."),
}

for target, note in NOTES.items():
    cmd = [PYBIN, "-m", "evovs_science.experience.store", "record",
           "--store", STORE, "--kind", "screening", "--target", target,
           "--payload", f"{DUAL}/{target}_dual_report.json", "--note", note]
    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stdout.strip() or result.stderr.strip())
