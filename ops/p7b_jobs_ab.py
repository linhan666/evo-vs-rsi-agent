#!/usr/bin/env python3
"""A/B the EVOVS_TRAIN_JOBS knob on one real ml.train invocation.

Requirement: the default (unset) must reproduce the recorded metrics exactly, and
a higher thread count must produce the same metrics faster. If the default does
not reproduce, the knob is not behaviour-neutral and must not be promoted.
"""
import json
import os
import shutil
import subprocess
import sys
import time

ROOT = "/home/linhan_cluster/evo_vs_rsi"
PY = os.path.join(ROOT, "scientific/.venv/bin/python")
TRACE = os.path.join(ROOT, "evolution/traces_p7b/p7b_4_drd2.json")
SANDBOX = os.path.join(ROOT, ".artifacts/shadow_p7b/cand1")
WORK = os.path.join(ROOT, ".artifacts/shadow_p7b/jobs_ab")

trace = json.load(open(TRACE, encoding="utf-8"))
train_steps = [s for s in trace["steps"]
               if s.get("tool_id") == "ml.train" and s.get("state") == "SUCCEEDED"]
if not train_steps:
    raise SystemExit("no successful ml.train step in the trace")

step = train_steps[0]
argv = list(step["argv"])
recorded = {a.get("path"): a.get("digest") for a in step.get("artifacts") or []}
print("argv:", " ".join(argv[:6]), "...")

results = {}
for label, jobs in (("default", None), ("jobs8", "8")):
    target = os.path.join(WORK, label)
    if os.path.exists(target):
        shutil.rmtree(target)
    shutil.copytree(SANDBOX, target, symlinks=True)
    env = dict(os.environ)
    env.pop("EVOVS_TRAIN_JOBS", None)
    if jobs:
        env["EVOVS_TRAIN_JOBS"] = jobs
    started = time.time()
    done = subprocess.run(argv, cwd=target, env=env, capture_output=True, text=True)
    wall = time.time() - started
    metrics_path = os.path.join(target, "runs", "probe_logreg", "metrics.json")
    metrics = {}
    for candidate in ("runs/probe_logreg/metrics.json", "runs/models/probe_logreg/metrics.json"):
        path = os.path.join(target, candidate)
        if os.path.exists(path):
            metrics = json.load(open(path, encoding="utf-8")).get("metrics") or {}
            break
    results[label] = {"exit": done.returncode, "wall": round(wall, 2), "metrics": metrics,
                      "stderr": done.stderr.strip().splitlines()[-1:] }
    print(label, "exit", done.returncode, "wall", round(wall, 2), "metrics", metrics,
          "" if done.returncode == 0 else done.stderr.strip().splitlines()[-1:])

base = results["default"]
fast = results["jobs8"]
same = base["metrics"] == fast["metrics"] and base["metrics"]
print()
print("metrics identical:", bool(same))
if base["wall"] and fast["wall"]:
    print("speedup: %.2fx" % (base["wall"] / fast["wall"]))
print("recorded metrics in trace:", json.dumps(step.get("metrics") or {})[:160])
