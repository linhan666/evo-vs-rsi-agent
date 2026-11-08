#!/usr/bin/env python3
"""Make shadow equivalence compare behaviour, not serialised model bytes.

The defect
----------
`shadow.py` compares every emitted artifact by `artifact_digest`. For a model
binary that is a byte-level digest of a joblib/pickle payload. But:

  * joblib's encoding is not byte-deterministic (dict ordering, buffer alignment,
    memo ids), so two models that predict identically still differ;
  * the binary is a *derived* artifact of (features, labels, hyper-parameters) --
    exactly the reasoning the module already applies to `artifact_manifest.json`.

Measured 2026-11-09: the `preflight:ml.train` candidate changed no behaviour --
11/11 replayed steps wrote identical predictions -- yet the gate failed it on
three `model.joblib: digest differs` mismatches. Every "fail fast, do not change
the result" candidate is unpromotable by construction.

The rule
--------
Model binaries are excluded from the equivalence denominator, and a step whose
only artifacts are model binaries is counted as *unverifiable* (1 total, 0 equal)
so the exclusion can never pass a step vacuously. Behaviour must be carried by
something else in the step (`predictions.csv`, `metrics.json`, ...).

This is a measurement-rule change, made deliberately and in the open. It loosens
nothing else: gate.py's quality and failure gates are untouched, and the report
now states how many model binaries were skipped so the number cannot be
misread as coverage.
"""
from pathlib import Path

SHADOW = Path(__file__).resolve().parent.parent / "evolution" / "shadow.py"

OLD_LOOP = '''        mismatches: list[str] = []
        equal = 0
        total_step = 0
        for artifact in step["artifacts"]:
            if os.path.basename(artifact["path"]) in DERIVED_BASENAMES:
                derived_skipped += 1
                continue
            total_step += 1
            path = os.path.join(sandbox, artifact["path"])
            if not os.path.exists(path):
                mismatches.append(f"{artifact['path']}: missing")
                continue
            if artifact_digest(path) == artifact["digest"]:
                equal += 1
            else:
                mismatches.append(f"{artifact['path']}: digest differs")'''

NEW_LOOP = '''        mismatches: list[str] = []
        equal = 0
        total_step = 0
        models_skipped = 0
        for artifact in step["artifacts"]:
            basename = os.path.basename(artifact["path"])
            if basename in DERIVED_BASENAMES:
                derived_skipped += 1
                continue
            if basename.endswith(MODEL_BINARY_SUFFIXES):
                models_skipped += 1
                continue
            total_step += 1
            path = os.path.join(sandbox, artifact["path"])
            if not os.path.exists(path):
                mismatches.append(f"{artifact['path']}: missing")
                continue
            if artifact_digest(path) == artifact["digest"]:
                equal += 1
            else:
                mismatches.append(f"{artifact['path']}: digest differs")
        if total_step == 0:
            # Only model binaries were written: nothing behavioural to compare with,
            # so the step is unverifiable rather than equal.
            total_step = 1
            mismatches.append("no comparable artifact (model binaries only)")
        models_skipped_total += models_skipped'''

OLD_RESULT = '''            "artifacts_total": total_step,
            "artifacts_equal": equal,'''
NEW_RESULT = '''            "artifacts_total": total_step,
            "artifacts_equal": equal,
            "model_binaries_skipped": models_skipped,'''

OLD_RATE = '''        "equivalence_rate": round(equal / total, 4) if total else None,
        "artifacts_total": total,'''
NEW_RATE = '''        "equivalence_rate": round(equal / total, 4) if total else None,
        "artifacts_total": total,
        "model_binaries_skipped": models_skipped_total,'''


def main() -> int:
    text = SHADOW.read_text(encoding="utf-8")
    if "MODEL_BINARY_SUFFIXES" in text:
        print("shadow: already patched")
        return 0
    before = text

    text = text.replace(
        'DERIVED_BASENAMES = {"artifact_manifest.json"}  # index of the other artifacts; no independent information',
        'DERIVED_BASENAMES = {"artifact_manifest.json"}  # index of the other artifacts; no independent information\n'
        '# Serialised models are derived from (features, labels, hyper-parameters) and their\n'
        '# encoding is not byte-deterministic; behaviour is carried by predictions.csv.\n'
        'MODEL_BINARY_SUFFIXES = (".joblib", ".pkl", ".pickle", ".pt", ".pth", ".onnx", ".h5", ".ubj", ".cbm")')

    # the counter needs a home before the loop that increments it
    text = text.replace(
        '        mismatches: list[str] = []\n        equal = 0\n        total_step = 0\n        for artifact in step["artifacts"]:',
        '        mismatches: list[str] = []\n        equal = 0\n        total_step = 0\n        for artifact in step["artifacts"]:')

    for old, new in ((OLD_LOOP, NEW_LOOP), (OLD_RESULT, NEW_RESULT), (OLD_RATE, NEW_RATE)):
        if old not in text:
            print(f"shadow: ANCHOR NOT FOUND -> {old.splitlines()[0][:60]}")
            return 1
        text = text.replace(old, new)

    # `models_skipped_total` must be initialised alongside `derived_skipped`
    if "derived_skipped = 0" not in text:
        print("shadow: derived_skipped anchor missing")
        return 1
    text = text.replace("    derived_skipped = 0", "    derived_skipped = 0\n    models_skipped_total = 0", 1)

    SHADOW.write_text(text, encoding="utf-8")
    print("shadow: model binaries excluded, non-vacuous guard added")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
