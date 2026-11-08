#!/usr/bin/env python3
"""Promote v7: EVOVS_TRAIN_JOBS default 1 -> 8.

Gate evidence (.artifacts/shadow_p7b/train_jobs_verdict2.json):
  equivalence pass (1.0) · cost pass (time ratio 1.394, best step 1.717)
  success pass · failure n/a · quality n/a · safety pass (canary intact)
  verdict: pass, blocking: [], needs_human_number: []

The knob itself was added earlier with default "1" (behaviour-neutral). Promotion
flips the default, which is the only thing that changes behaviour, and records the
entry in evolution/versions.json.
"""
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TRAIN = ROOT / "scientific" / "src" / "evovs_science" / "modeling" / "train.py"
VERSIONS = ROOT / "evolution" / "versions.json"


def main() -> int:
    text = TRAIN.read_text(encoding="utf-8")
    old = 'raw = os.environ.get("EVOVS_TRAIN_JOBS", "1").strip()'
    new = 'raw = os.environ.get("EVOVS_TRAIN_JOBS", "8").strip()   # v7: promoted 2026-11-09'
    if old not in text:
        print("train.py: default already flipped or anchor missing")
        return 1
    TRAIN.write_text(text.replace(old, new), encoding="utf-8")
    print("train.py: EVOVS_TRAIN_JOBS default -> 8")

    ledger = json.loads(VERSIONS.read_text(encoding="utf-8"))
    if any(e.get("version") == "v7" for e in ledger["entries"]):
        print("versions.json: v7 already recorded")
        return 0

    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                         capture_output=True, text=True).stdout.strip()
    ledger["entries"].append({
        "version": "v7",
        "candidate_id": "auto-train-jobs-p7b",
        "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git_sha": sha,
        "status": "active",
        "change": {"type": "env", "key": "EVOVS_TRAIN_JOBS", "value": "8"},
        "gate": {"verdict": "pass", "blocking": [], "needs_human_number": []},
        "rollback": 'set the EVOVS_TRAIN_JOBS default back to "1" in '
                    'scientific/src/evovs_science/modeling/train.py; the knob is the only change',
        "note": "First candidate derived from this round's own traces (9 p7b tickets). "
                "RandomForest/XGBoost were pinned to n_jobs=1 and CatBoost to its default thread "
                "count; all three are deterministic given random_state, so this trades cores for "
                "wall time only. Shadow replay over 11 real ml.train steps: equivalence 1.0, "
                "57.38s -> 41.22s (1.394x, best step 1.717x). A/B on p7b_4_drd2: 3.42s -> 1.89s "
                "with byte-identical metrics.",
    })
    VERSIONS.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("versions.json: v7 appended")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
