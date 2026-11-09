#!/usr/bin/env python3
"""Phase 7 sequential driver: run one group's targets strictly one after another.

Why this exists
---------------
The Phase 7 protocol compares four arms (W/A/M/R) over the same 9 targets,
*sequentially*, because experience transfer only happens if target N+1 starts
after target N has recorded its experience. Manually dropping the next task
file makes the chain depend on a human noticing that the previous target
finished, and a task submitted while its predecessor still runs would execute
in parallel and destroy the transfer premise.

The driver is idempotent and restartable:

  * it walks the canonical sequence order;
  * a target whose ticket already reached a terminal state is skipped;
  * a target whose ticket is still running is waited on;
  * only when no ticket is open does it submit the next task file.

Experience accounting
---------------------
`experience.retrieve` is the only experience tool the agent has; nothing in the
harness writes the store. So for the memory arms (M and R) this driver distils
each finished target into two records — `dataset` (the data profile) and
`model` (the winning configuration) — from the ticket's own artifacts, and
appends them to the store before the next target is submitted. That is the
same operator-side accounting Phase 6 used via record_evidence_bundle.py, now
automatic. Group A never sees the store (the tool is hidden for `fixed`) and
group W has no agent, so neither writes it.

Usage
-----
  python3 ops/phase7_seq.py --group r
  python3 ops/phase7_seq.py --group r --dry-run
  python3 ops/phase7_seq.py --group r --from mor --no-record
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE_DB = ROOT / ".artifacts" / "state" / "orchestrator.sqlite"
INBOX = ROOT / ".artifacts" / "inbox"
TASKS = ROOT / "ops" / "phase7_custom"   # overridden by --tasks-dir
RUNS = ROOT / "ops" / "phase7_runs"
DATA_ROOT = ROOT / "scientific" / ".artifacts"
STORE = DATA_ROOT / "experience" / "experience.json"   # overridden by --store
PAYLOADS = DATA_ROOT / "experience" / "payloads"
VENV_PY = ROOT / "scientific" / ".venv" / "bin" / "python"

# Canonical Phase 7 sequence, numbered 1..9 exactly as written into the task text.
# oprm1 / oprk1 task files are stale duplicates of mor / kor and are excluded.
ORDER = ["d2", "5ht", "adr", "drd2", "mor", "cbr", "kor", "ca2", "pt"]

TARGET_META = {
    "d2": {"name": "D2", "slug": "d(2)_dopamine_recept", "class": "GPCR"},
    "5ht": {"name": "5HT", "slug": "5-hydroxytryptamine_", "class": "GPCR"},
    "adr": {"name": "ADR", "slug": "adenosine_receptor_a", "class": "GPCR"},
    "drd2": {"name": "DRD2", "slug": "drd2", "class": "GPCR"},
    "mor": {"name": "MOR", "slug": "oprm1", "class": "GPCR"},
    "cbr": {"name": "CBR", "slug": "cannabinoid_receptor", "class": "GPCR"},
    "kor": {"name": "KOR", "slug": "oprk1", "class": "GPCR"},
    "ca2": {"name": "CA2", "slug": "carbonic_anhydrase_2", "class": "enzyme"},
    "pt": {"name": "PT", "slug": "prothrombin", "class": "enzyme"},
}

DONE = {"ready", "done", "completed", "succeeded"}
BAD = {"failed", "error", "cancelled", "canceled", "aborted", "rejected"}

# Models refit on all data after selection; their stored metrics are in-sample and
# must never be reported as validation performance.
REFIT_PREFIXES = ("final_",)


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%SZ")


def log(message: str) -> None:
    print(f"[{stamp()}] {message}", flush=True)


def read_ticket(task_id: str) -> dict | None:
    """Return the newest ticket whose mandate scope (or channel thread) names `task_id`."""
    if not STATE_DB.exists():
        return None
    try:
        con = sqlite3.connect(f"file:{STATE_DB}?mode=ro", uri=True, timeout=10)
    except sqlite3.Error:
        return None
    try:
        rows = con.execute("SELECT value FROM ticket").fetchall()
    except sqlite3.Error:
        return None
    finally:
        con.close()

    newest = None
    for (value,) in rows:
        try:
            payload = json.loads(value)
        except (TypeError, ValueError):
            continue
        basis = (payload.get("mandate") or {}).get("basis") or {}
        scope = basis.get("scope")
        named = isinstance(scope, dict) and scope.get("taskId") == task_id
        if not named:
            named = any(ch.get("thread") == f"local:{task_id}" for ch in payload.get("channels") or [])
        if not named:
            continue
        if newest is None or str(payload.get("createdAt", "")) >= str(newest.get("createdAt", "")):
            newest = payload
    if newest is None:
        return None

    assignments = newest.get("assignments") or []
    latest = assignments[-1] if assignments else {}
    report = latest.get("report") or {}
    return {
        "ticket_id": newest.get("id"),
        "title": newest.get("title", ""),
        "state": report.get("state") or latest.get("state") or ("assigned" if assignments else "submitted"),
        "started_at": latest.get("startedAt"),
        "ended_at": latest.get("endedAt"),
        "summary": report.get("summary", ""),
        "directory": (newest.get("execution") or {}).get("directory", ""),
        "n_assignments": len(assignments),
    }


def is_terminal(state: str) -> bool:
    return state in DONE or state in BAD


def submit(group: str, task_id: str, dry_run: bool = False) -> bool:
    """Copy the task file into the inbox atomically so the watcher never sees a half-written file.

    `task_id` already carries the group prefix (seq_r_d2); a retry suffix (_r1) reuses
    the original task file so the payload is identical apart from the id.
    """
    base = re.sub(r"_r\d+$", "", task_id)
    source = TASKS / f"{base}.json"
    if not source.exists():
        log(f"MISSING task file {source}")
        return False
    if dry_run:
        log(f"DRY-RUN would submit {source.name}")
        return True
    INBOX.mkdir(parents=True, exist_ok=True)
    staging = INBOX / f".{task_id}.json.tmp"
    shutil.copyfile(source, staging)
    os.replace(staging, INBOX / f"{task_id}.json")
    log(f"submitted {source.name} -> inbox/{task_id}.json")
    return True


def job_records(workdir: Path) -> list[dict]:
    """Every finished job of the ticket, oldest first."""
    records = []
    for path in glob_results(workdir):
        try:
            records.append(json.loads(path.read_text(encoding="utf-8")))
        except (ValueError, OSError):
            continue
    records.sort(key=lambda item: str(item.get("created_at", "")))
    return records


def glob_results(workdir: Path) -> list[Path]:
    if not workdir.exists():
        return []
    return sorted((workdir / ".jobs").glob("*/result.json"))


def job_counts(workdir: Path) -> tuple[int, int]:
    index = workdir / ".jobs" / "index.json"
    if not index.exists():
        return 0, 0
    try:
        payload = json.loads(index.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return 0, 0
    values = list(payload.values()) if isinstance(payload, dict) else list(payload)
    return len(values), sum(1 for item in values if item.get("state") != "SUCCEEDED")


def model_table(workdir: Path, jobs: list[dict]) -> dict[str, dict]:
    """Parsed metrics.json per model directory, keyed by the split each model was trained on.

    `metrics.json` stores `split_strategy` as the literal string "scaffold-manifest"
    for every model, so it cannot tell a random split from a scaffold one. The real
    distinction lives in the `ml.train` argv (`--split-manifest splits/<target>_X.json`),
    so the split kind is recovered from there.
    """
    manifests: dict[str, str] = {}
    strategies: dict[str, str] = {}
    for job in jobs:
        if job.get("state") != "SUCCEEDED":
            continue
        argv = [item for item in job.get("argv") or [] if isinstance(item, str)]
        kv = {}
        for position, item in enumerate(argv):
            if item.startswith("--") and position + 1 < len(argv):
                kv[item.lstrip("-")] = argv[position + 1]
        if job.get("tool_id") == "ml.train":
            out_dir = os.path.basename(str(kv.get("output-dir") or "").rstrip("/"))
            if out_dir and kv.get("split-manifest"):
                manifests[out_dir] = os.path.basename(str(kv["split-manifest"]))
        elif job.get("tool_id") == "data.split":
            produced = os.path.basename(str(kv.get("output") or ""))
            if produced and kv.get("strategy"):
                strategies[produced] = str(kv["strategy"]).lower()

    table: dict[str, dict] = {}
    if not workdir.exists():
        return table
    # The agent chooses its own output directory, so a fixed `models/*` glob misses
    # runs that wrote `model_*` at the workspace root. Walk everything except the
    # job bookkeeping tree, and key by directory name to join with `--output-dir`.
    for path in sorted(workdir.glob("**/metrics.json")):
        relative = path.relative_to(workdir)
        if ".jobs" in relative.parts:
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        metrics = payload.get("metrics") or {}
        counts = payload.get("counts") or {}
        name = relative.parent.name
        manifest = manifests.get(name, "")
        # Classification must not rely on the manifest file name: agents name their
        # own manifests (`drd2_scaffold.json`, but also `cbr_ki_split.json` for a
        # scaffold split). The authoritative source is the `data.split` job that
        # produced the file, where `--strategy` is recorded explicitly.
        # `metrics.json.split_strategy` is useless here: it reports
        # "scaffold-manifest" even for random splits.
        if re.search(r"final|refit", manifest):
            kind = "refit"        # retrained on all labelled data: metrics are in-sample
        elif strategies.get(manifest) in ("scaffold", "random"):
            kind = strategies[manifest]
        elif "frozen_" in manifest:
            kind = "scaffold"     # phase7b hands over a frozen scaffold-grouped manifest
        elif "scaffold" in manifest:
            kind = "scaffold"     # manifest name is the only remaining evidence
        elif manifest:
            kind = "other"        # a manifest we cannot attribute to a strategy
        else:
            kind = "internal"     # ml.train split internally, split kind unverified
        table[str(relative.parent)] = {
            "model": payload.get("model"),
            "seed": payload.get("seed"),
            "split_strategy": payload.get("split_strategy"),
            "split_manifest": manifest,
            "split_kind": kind,
            "auroc": metrics.get("auroc"),
            "auprc": metrics.get("auprc"),
            "ef_at_1pct": metrics.get("ef_at_1pct"),
            "ef_at_5pct": metrics.get("ef_at_5pct"),
            "n_joined": counts.get("joined"),
            "n_positives": counts.get("positives"),
            # Validation size is recorded because AUROC on a few hundred molecules is
            # noisy, and EF@1% on a small validation slice is not interpretable.
            "n_validation": counts.get("validation"),
            "n_validation_positives": counts.get("validation_positives"),
            "is_refit": kind == "refit" or name.startswith(REFIT_PREFIXES),
        }
    return table


def featurization_of(jobs: list[dict]) -> dict:
    """Last successful rdkit.featurize arguments — what representation the agent settled on."""
    chosen: dict = {}
    for job in jobs:
        if job.get("tool_id") != "rdkit.featurize" or job.get("state") != "SUCCEEDED":
            continue
        argv = [item for item in job.get("argv") or [] if isinstance(item, str)]
        kv = {}
        for position, item in enumerate(argv):
            if item.startswith("--") and position + 1 < len(argv):
                kv[item.lstrip("-")] = argv[position + 1]
        chosen = {"radius": kv.get("radius"), "n_bits": kv.get("n-bits"),
                  "desc_set": kv.get("desc-set"), "argv": argv}
    return chosen


USAGE_LOG_NAME: str | None = None
BUDGET_LIMIT: int | None = None   # search draws per ticket, set by --budget-limit


def token_usage(started: str | None, ended: str | None, group: str) -> dict:
    """Sum the LLM usage log over the ticket's wall-clock window.

    The usage hook appends one JSON line per completed model call, so tokens are
    attributed by timestamp rather than by ticket id. That is accurate enough for
    the macro comparison and needs no change to the service.
    """
    path = DATA_ROOT / (USAGE_LOG_NAME or f"usage_seq_{group}.jsonl")
    if not (started and ended and path.exists()):
        return {}
    try:
        begin = datetime.fromisoformat(started.replace("Z", "+00:00"))
        finish = datetime.fromisoformat(ended.replace("Z", "+00:00"))
    except ValueError:
        return {}

    calls = prompt = completion = cached = 0
    try:
        with path.open(encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    moment = datetime.fromisoformat(str(entry.get("ts", "")).replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    continue
                if not (begin <= moment <= finish):
                    continue
                calls += 1
                prompt += entry.get("prompt_tokens") or 0
                completion += entry.get("completion_tokens") or 0
                cached += entry.get("cached_tokens") or 0
    except OSError:
        return {}
    return {"llm_calls": calls, "prompt_tokens": prompt, "completion_tokens": completion,
            "cached_tokens": cached, "total_tokens": prompt + completion}


def collect(group: str, entry: dict, task_id: str, ticket: dict, label: str = "") -> dict:
    """Gather the macro indicators for one finished target and persist the agent's report."""
    workdir = Path(ticket.get("directory") or "")
    jobs_total, jobs_failed = job_counts(workdir) if workdir.exists() else (0, 0)
    jobs = job_records(workdir)
    models = model_table(workdir, jobs)

    # Validation comparison excludes refits, whose stored metrics are in-sample.
    # Random splits are reported but never selected as the lesson to transfer: a
    # random split leaks near-duplicate scaffolds across the split and inflates
    # AUROC, so using it as the experience recommendation would poison every
    # later target's numbers.
    ranked = [(info["auroc"], name, info) for name, info in models.items()
              if not info["is_refit"] and isinstance(info["auroc"], (int, float))]
    ranked.sort(reverse=True)
    scaffold_ranked = [row for row in ranked if row[2].get("split_kind") == "scaffold"]

    best_auroc, best_model, best_info = (ranked[0][0], ranked[0][1], ranked[0][2]) if ranked else (None, None, {})
    s_best = scaffold_ranked[0] if scaffold_ranked else None

    top100: list[str] = []
    screening_outputs: list[str] = []
    if workdir.exists():
        for pattern in ("**/*top100*", "**/*top_100*", "**/*topK*"):
            top100.extend(str(path.relative_to(workdir)) for path in workdir.glob(pattern))
        for pattern in ("**/*ranked*", "**/*top*", "**/*screening*"):
            screening_outputs.extend(str(path.relative_to(workdir)) for path in workdir.glob(pattern))

    wall = None
    if ticket.get("started_at") and ticket.get("ended_at"):
        try:
            start = datetime.fromisoformat(ticket["started_at"].replace("Z", "+00:00"))
            end = datetime.fromisoformat(ticket["ended_at"].replace("Z", "+00:00"))
            wall = round((end - start).total_seconds(), 1)
        except ValueError:
            pass

    record = {
        "group": group,
        "budget_limit": BUDGET_LIMIT,
        "seq": entry["seq"],
        "target": entry["target"],
        "task_id": task_id,
        "ticket_id": ticket.get("ticket_id"),
        "state": ticket.get("state"),
        "wall_seconds": wall,
        "jobs_total": jobs_total,
        "jobs_failed": jobs_failed,
        "models": sorted(models),
        "best_model": best_model,
        "best_auroc": best_auroc,
        "best_auprc": (best_info or {}).get("auprc"),
        "best_ef_at_1pct": (best_info or {}).get("ef_at_1pct"),
        "best_scaffold_model": s_best[1] if s_best else None,
        "best_scaffold_auroc": s_best[0] if s_best else None,
        "best_scaffold_auprc": s_best[2].get("auprc") if s_best else None,
        "best_scaffold_ef_at_1pct": s_best[2].get("ef_at_1pct") if s_best else None,
        "refit_models_excluded": sorted(name for name, info in models.items() if info["is_refit"]),
        "model_table": models,
        "featurization": featurization_of(jobs),
        "top100": sorted(set(top100)),
        "screening_outputs": sorted(set(screening_outputs)),
        "tokens": token_usage(ticket.get("started_at"), ticket.get("ended_at"), group),
        "workdir": str(workdir),
        "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    RUNS.mkdir(parents=True, exist_ok=True)
    stem = f"{group}_{entry['seq']:02d}_{entry['target']}" + (f"_{label}" if label else "")
    (RUNS / f"{stem}.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    (RUNS / f"{stem}.report.md").write_text(
        f"# {group.upper()} #{entry['seq']} {entry['target']}\n\n"
        f"- task: `{task_id}`\n- ticket: `{ticket.get('ticket_id')}`\n- state: {ticket.get('state')}\n"
        f"- wall: {wall}s, jobs {jobs_total} (failed {jobs_failed}), models {len(models)}\n"
        f"- best validation model (any split): {best_model} AUROC={best_auroc} AUPRC={(best_info or {}).get('auprc')} "
        f"EF@1%={(best_info or {}).get('ef_at_1pct')}\n"
        f"- best scaffold model: {record['best_scaffold_model']} AUROC={record['best_scaffold_auroc']} "
        f"EF@1%={record['best_scaffold_ef_at_1pct']}\n"
        f"- refits excluded from ranking: {record['refit_models_excluded']}\n"
        f"- top-100 artifacts: {len(record['top100'])}\n\n"
        f"## agent report\n\n{ticket.get('summary') or '(empty)'}\n",
        encoding="utf-8",
    )
    return record


def dataset_profile(slug: str) -> dict:
    """Sample count and positive rate straight from the read-only label file."""
    path = DATA_ROOT / "chembl" / slug / "ki" / "dataset.csv"
    if not path.exists():
        return {}
    total = positives = 0
    try:
        with path.open(encoding="utf-8", errors="ignore") as handle:
            header = handle.readline().strip().split(",")
            column = header.index("label") if "label" in header else -1
            for line in handle:
                if not line.strip():
                    continue
                total += 1
                if column >= 0:
                    parts = line.rstrip("\n").split(",")
                    if column < len(parts) and parts[column].strip() in ("1", "1.0", "True", "true"):
                        positives += 1
    except OSError:
        return {}
    return {"n_samples": total, "n_positives": positives,
            "positive_rate": round(positives / total, 4) if total else None}


def already_recorded(group: str, seq: int, target: str, kind: str) -> bool:
    """True when this target's record of `kind` is already in the store.

    Restarting the driver re-collects finished targets, and without this guard the
    same target would be appended twice, duplicating what later targets retrieve.
    """
    if not STORE.exists():
        return False
    try:
        records = json.loads(STORE.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return False
    for item in records:
        payload = item.get("payload") or {}
        if (item.get("kind") == kind and payload.get("group") == group
                and payload.get("sequence_index") == seq and payload.get("target") == target):
            return True
    return False


def record_experience(group: str, entry: dict, record: dict) -> None:
    """Distil the finished target into dataset + model records so the next target can reuse it.

    Skipped for groups whose agents cannot read the store (A is `fixed`, W has no agent).
    """
    if group not in ("m", "r"):
        return
    if not VENV_PY.exists():
        log("experience record skipped: venv python missing")
        return
    meta = TARGET_META[entry["target"]]
    profile = dataset_profile(meta["slug"])
    # Transfer the scaffold-split winner: a random-split winner is an artefact of
    # near-duplicate leakage between train and validation.
    chosen_name = record.get("best_scaffold_model") or record.get("best_model") or ""
    best = record.get("model_table", {}).get(chosen_name, {})
    featurization = record.get("featurization") or {}

    PAYLOADS.mkdir(parents=True, exist_ok=True)
    written = []
    for kind, payload in (
        ("dataset", {
            "schema": "phase7_experience_v1",
            "kind": "dataset",
            "target": meta["name"],
            "target_slug": meta["slug"],
            "target_class": meta["class"],
            "endpoint": "Ki",
            "sequence_index": entry["seq"],
            "group": group,
            "characteristics": profile,
            "label_file": f"scientific/.artifacts/chembl/{meta['slug']}/ki/dataset.csv",
            "note": "Binary label column taken as supplied; no re-thresholding.",
        }),
        ("model", {
            "schema": "phase7_experience_v1",
            "kind": "model",
            "target": meta["name"],
            "target_slug": meta["slug"],
            "target_class": meta["class"],
            "endpoint": "Ki",
            "sequence_index": entry["seq"],
            "group": group,
            "characteristics": profile,
            "best_configuration": {
                "model": best.get("model") or record.get("best_model"),
                "seed": best.get("seed"),
                "split_strategy": best.get("split_strategy"),
                "featurization": {k: featurization.get(k) for k in ("radius", "n_bits", "desc_set")},
                "metrics": {
                    "auroc": best.get("auroc"),
                    "auprc": best.get("auprc"),
                    "ef_at_1pct": best.get("ef_at_1pct"),
                },
                "evaluation": "scaffold-manifest validation split (not the locked test set)",
            },
            "rejected": [
                {"model": info.get("model"), "name": name, "auroc": info.get("auroc"),
                 "ef_at_1pct": info.get("ef_at_1pct"),
                 "reason": "lower validation AUROC than the selected model"                }
                for name, info in sorted(record.get("model_table", {}).items(),
                                         key=lambda kv: -(kv[1].get("auroc") or 0))
                if name != chosen_name and not info.get("is_refit")
                and info.get("split_kind") == "scaffold"
            ][:6],
            "code_pattern": {
                "featurize_args": " ".join(
                    f"--{k.replace('_', '-')} {v}" for k, v in
                    (("radius", featurization.get("radius")), ("n-bits", featurization.get("n_bits")),
                     ("desc-set", featurization.get("desc_set"))) if v is not None),
                "jobs_total": record.get("jobs_total"),
                "jobs_failed": record.get("jobs_failed"),
                "wall_seconds": record.get("wall_seconds"),
                "reusable": True,
            },
            "source_ticket": record.get("ticket_id"),
        }),
    ):
        if already_recorded(group, entry["seq"], meta["name"], kind):
            log(f"experience {kind} for {meta['name']} already recorded; not duplicating")
            continue
        path = PAYLOADS / f"{group}_{entry['seq']:02d}_{entry['target']}_{kind}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        note = (
            f"Applicable to ChEMBL Ki binary sets of ~{profile.get('n_samples', '?')} molecules at "
            f"{profile.get('positive_rate', '?')} positive rate, scaffold split; re-check before "
            f"applying to much smaller or balanced datasets."
        )
        result = subprocess.run(
            [str(VENV_PY), "-m", "evovs_science.experience.store", "record",
             "--kind", kind, "--target", meta["name"], "--payload", str(path),
             "--note", note, "--store", str(STORE)],
            cwd=str(ROOT), capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            log(f"experience record failed ({kind}): {(result.stderr or '').strip().splitlines()[-1:]}")
        else:
            written.append(result.stdout.strip())
    if written:
        log(f"experience recorded for {meta['name']}: {'; '.join(written)}")


def run_code_metrics(group: str, workdir: str, target: str, label: str = "") -> None:
    """Micro-level code indicators. A failure here must never stop the sequence."""
    if not workdir:
        return
    script = ROOT / "ops" / "code_metrics.py"
    if not script.exists():
        return
    RUNS.mkdir(parents=True, exist_ok=True)
    out = RUNS / (f"{group}_{target}" + (f"_{label}" if label else "") + ".code.json")
    try:
        result = subprocess.run([sys.executable, str(script), "--ticket", workdir, "--output", str(out)],
                                capture_output=True, text=True, timeout=180)
        if result.returncode != 0:
            tail = (result.stderr or "").strip().splitlines()[-1:]
            log(f"code_metrics failed for {target}: {tail}")
        else:
            log(f"code_metrics -> {out.name}")
    except (subprocess.SubprocessError, OSError) as error:
        log(f"code_metrics error for {target}: {error}")


def plan(group: str, prefix: str = "seq") -> list[dict]:
    return [{"seq": number, "target": target, "task_id": f"{prefix}_{group}_{target}"}
            for number, target in enumerate(ORDER, start=1)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="phase7 sequential driver")
    parser.add_argument("--group", required=True, choices=["r", "a", "m", "w"])
    parser.add_argument("--from", dest="start_at", default=None, help="begin the walk at this target slug")
    parser.add_argument("--only", default=None, help="process a single target slug")
    parser.add_argument("--poll", type=float, default=30.0, help="seconds between status checks")
    parser.add_argument("--timeout", type=float, default=7200.0, help="per-target wall clock limit")
    parser.add_argument("--retries", type=int, default=1, help="resubmissions after a failed state")
    parser.add_argument("--no-record", action="store_true", help="do not write experience records")
    parser.add_argument("--task-id", dest="task_id_override", default=None,
                        help="submit under this task id instead of seq_<group>_<target> (single target only)")
    parser.add_argument("--label", default="",
                        help="suffix for record filenames, so a replay never overwrites the lineage record")
    parser.add_argument("--prefix", default="seq",
                        help="task-id prefix; round 7 used 'seq', the redesigned round uses 'p7b'")
    parser.add_argument("--tasks-dir", default=None,
                        help="directory holding the task JSONs (default ops/phase7_custom)")
    parser.add_argument("--store", default=None,
                        help="experience store path; each memory-bearing arm needs its own file")
    parser.add_argument("--usage-log", default=None,
                        help="ledger file under scientific/.artifacts, e.g. usage_p7b_r.jsonl")
    parser.add_argument("--budget-limit", type=int, default=None,
                        help="search draws allowed per ticket; recorded so the analysis can "
                             "tell `budget_exhausted` from `stopped_early`")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    global TASKS, STORE, USAGE_LOG_NAME, BUDGET_LIMIT
    if args.usage_log:
        USAGE_LOG_NAME = args.usage_log
    if args.budget_limit:
        BUDGET_LIMIT = args.budget_limit
    if args.tasks_dir:
        TASKS = (ROOT / args.tasks_dir) if not args.tasks_dir.startswith("/") else Path(args.tasks_dir)
    if args.store:
        STORE = Path(args.store)

    entries = plan(args.group, args.prefix)
    if args.start_at:
        slugs = [entry["target"] for entry in entries]
        if args.start_at not in slugs:
            parser.error(f"--from must be one of {slugs}")
        entries = entries[slugs.index(args.start_at):]
    if args.only:
        entries = [entry for entry in entries if entry["target"] == args.only]
        if not entries:
            parser.error(f"--only must be one of {ORDER}")
    if args.task_id_override:
        if len(entries) != 1:
            parser.error("--task-id requires --only with exactly one target")
        entries[0]["task_id"] = args.task_id_override

    log(f"group={args.group} sequence={[entry['target'] for entry in entries]}")

    for entry in entries:
        attempt = 0
        task_id = entry["task_id"]
        deadline = time.monotonic() + args.timeout

        while True:
            ticket = read_ticket(task_id)

            if ticket is None:
                if args.dry_run:
                    log(f"#{entry['seq']} {entry['target']} would be submitted")
                    break
                if not submit(args.group, task_id):
                    return 1
                time.sleep(args.poll)
                continue

            if is_terminal(ticket["state"]):
                if ticket["state"] in BAD:
                    if attempt < args.retries:
                        attempt += 1
                        task_id = f"{entry['task_id']}_r{attempt}"
                        log(f"#{entry['seq']} {entry['target']} ended {ticket['state']}; retrying as {task_id}")
                        if not submit(args.group, task_id, args.dry_run):
                            return 1
                        deadline = time.monotonic() + args.timeout
                        continue
                    RUNS.mkdir(parents=True, exist_ok=True)
                    (RUNS / f"{args.group}_{entry['seq']:02d}_{entry['target']}.failed.json").write_text(
                        json.dumps({**entry, "task_id": task_id, "ticket_id": ticket["ticket_id"],
                                    "state": ticket["state"], "note": "gave up after retries"},
                                   ensure_ascii=False, indent=2), encoding="utf-8")
                    log(f"#{entry['seq']} {entry['target']} FAILED permanently; continuing")
                    break

                record = collect(args.group, entry, task_id, ticket, args.label)
                log(f"#{entry['seq']} {entry['target']} DONE state={record['state']} "
                    f"wall={record['wall_seconds']}s jobs={record['jobs_total']} "
                    f"best={record['best_model']}({record['best_auroc']}) "
                    f"scaffold={record['best_scaffold_model']}({record['best_scaffold_auroc']}) "
                    f"top100={len(record['top100'])}")
                if not args.no_record:
                    record_experience(args.group, entry, record)
                run_code_metrics(args.group, ticket.get("directory", ""), entry["target"], args.label)
                break

            if time.monotonic() > deadline:
                log(f"#{entry['seq']} {entry['target']} TIMEOUT after {args.timeout}s (state={ticket['state']}); "
                    f"ticket left untouched")
                return 2

            log(f"#{entry['seq']} {entry['target']} waiting (state={ticket['state']}, "
                f"assigned {ticket['n_assignments']}x)")
            if args.dry_run:
                break
            time.sleep(args.poll)

    log("sequence complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
