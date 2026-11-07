#!/usr/bin/env python3
"""Rewrite Phase 7 task texts so each arm states the truth about its own memory.

Two defects in the generated Phase 7 task files are fixed here:

1. The experience store path was never given to the agent. `experience.retrieve`
   takes a required `store` argument, and a wrong or missing path silently
   returns zero records, so the memory arms were reading an empty store. The
   canonical absolute path is now stated in the constraints.

2. Group A runs with `EVOVS_GROUP=fixed`, which removes the `experience.retrieve`
   tool entirely, yet its task text still ordered the agent to call it. A now
   states plainly that this arm has no memory, so the no-memory baseline does not
   pay for a tool call that cannot succeed.

The `/n` typo that glued the first constraint onto the word "Constraints:" is
also repaired. `seq_r_d2.json` is left untouched: that target already ran.

Usage:  python3 ops/phase7_texts.py [--check]
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

TASKS = Path(__file__).resolve().parent / "phase7_custom"
STORE = "/home/linhan_cluster/evo_vs_rsi/scientific/.artifacts/experience/experience.json"

# d2 already ran with the original text; rewriting it would misrepresent that run.
FROZEN = {"seq_r_d2"}

TARGETS = ["5ht", "adr", "drd2", "mor", "cbr", "kor", "ca2", "pt", "d2"]

MEMORY_BODY = """Constraints:
- labels: {labels} (read-only)
- library: {library}
- experience store: {store} (read-only; pass this absolute path as the `store` argument of experience.retrieve — a wrong or missing path silently returns zero records)
- this is target #{seq} in a sequence of 9; earlier targets in this sequence have been modelled already

IMPORTANT: Before choosing your modelling approach, retrieve prior experience (experience.retrieve) from that store and reuse any configuration that fits this dataset's characteristics (sample size, positive rate, target class). The store holds nothing for target #1 and gains one dataset record plus one model record each time a target completes, so read it again for every target. Only explore new configurations if prior experience does not cover this data profile.

You may choose representation, model family, validation strategy, and fusion.

Deliverable: report with (a) choices and rationale, (b) AUROC/AUPRC/EF@1%, (c) top-100 path, (d) cost, (e) which experience_id(s) you used, and what you reused verbatim versus adapted."""

NOMEM_BODY = """Constraints:
- labels: {labels} (read-only)
- library: {library}
- this is target #{seq} in a sequence of 9
- no prior-experience store is available in this arm and there is no experience.retrieve tool: derive everything from first principles

IMPORTANT: This arm carries no cross-target memory. Derive your modelling approach from the dataset in front of you (sample size, positive rate, target class) rather than from earlier targets.

You may choose representation, model family, validation strategy, and fusion.

Deliverable: report with (a) choices and rationale, (b) AUROC/AUPRC/EF@1%, (c) top-100 path, (d) cost, (e) what you would reuse if you had to model another target of this kind."""


def rebuild(text: str, memory: bool) -> str:
    goal = text.split("\n", 1)[0].strip()
    labels = re.search(r"labels:\s*(\S+)", text)
    library = re.search(r"library:\s*(\S+)", text)
    seq = re.search(r"target #(\d+)", text)
    if not (labels and library and seq):
        raise ValueError("unparsable task text")
    body = (MEMORY_BODY if memory else NOMEM_BODY).format(
        labels=labels.group(1), library=library.group(1), store=STORE, seq=seq.group(1))
    return goal + "\n\n" + body + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="report without writing")
    args = parser.parse_args()

    changed = skipped = 0
    for group, memory in (("r", True), ("m", True), ("a", False)):
        for target in TARGETS:
            path = TASKS / f"seq_{group}_{target}.json"
            if not path.exists():
                print(f"missing {path.name}")
                continue
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload["task_id"] in FROZEN:
                print(f"skip  {path.name} (already ran with the original text)")
                skipped += 1
                continue
            fresh = rebuild(payload["text"], memory)
            if args.check:
                print(f"check {path.name}: {len(payload['text'])} -> {len(fresh)} chars")
                continue
            payload["text"] = fresh
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            changed += 1

    print(f"\nrewrote {changed}, skipped {skipped}")
    if not args.check:
        stale = sorted(p.name for p in TASKS.glob("seq_w_*.json"))
        print(f"W group task files left untouched ({len(stale)}): W is driven by ops/phase6_workflow.py, not the agent inbox")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
