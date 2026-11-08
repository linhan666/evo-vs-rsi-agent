#!/usr/bin/env python3
"""Expose tree-model parallelism as `EVOVS_TRAIN_JOBS`, default 1.

Why a knob and not a hard-coded change
--------------------------------------
`evolution/shadow.py` builds its env delta from `changes[type == "env"]` only:
a candidate whose change is any other type is replayed against the *current*
code, so it can never be verified. That is why every promotable entry in
`evolution/versions.json` is an env change (v1 was `EVOVS_FEAT_JOBS=8`).

`build_model` hard-codes `n_jobs=1` for RandomForest and XGBoost, and leaves
CatBoost at its default thread count. All three are deterministic given
`random_state` regardless of thread count, so parallelism changes wall time and
nothing else — exactly the shape a cost candidate needs.

Default stays "1", so this edit is behaviour-neutral until a candidate is
promoted. That matters because the M arm is mid-run on this code.

Rollback: delete `_train_jobs` and restore the literal `n_jobs=1` arguments.
"""
from pathlib import Path

TRAIN = Path(__file__).resolve().parent.parent / "scientific" / "src" / "evovs_science" / "modeling" / "train.py"

HELPER = '''MODELS = ("logreg", "rf", "xgboost", "catboost")


def _train_jobs() -> int:
    """Thread count for the tree models.

    Default 1 preserves the historical behaviour exactly. RandomForest and
    XGBoost are deterministic given `random_state` for any thread count, so this
    knob trades wall time for cores and nothing else. It exists as an env var
    because shadow replay can only apply env-type candidates; a hard-coded change
    would be unverifiable and therefore unpromotable.
    """
    raw = os.environ.get("EVOVS_TRAIN_JOBS", "1").strip()
    try:
        value = int(raw)
    except ValueError:
        return 1
    return value if value != 0 else 1


'''


def main() -> int:
    text = TRAIN.read_text(encoding="utf-8")
    if "_train_jobs" in text:
        print("train.py: already patched")
        return 0
    before = text

    text = text.replace('MODELS = ("logreg", "rf", "xgboost", "catboost")\n\n\n', HELPER, 1)
    text = text.replace(
        'return RandomForestClassifier(n_estimators=200, random_state=seed, n_jobs=1)',
        'return RandomForestClassifier(n_estimators=200, random_state=seed, n_jobs=_train_jobs())')
    text = text.replace(
        'colsample_bytree=0.9, min_child_weight=1.0, random_state=seed, n_jobs=1,',
        'colsample_bytree=0.9, min_child_weight=1.0, random_state=seed, n_jobs=_train_jobs(),')
    text = text.replace(
        'return CatBoostClassifier(iterations=300, depth=6, learning_rate=0.1, random_seed=seed,\n'
        '                                  verbose=False, allow_writing_files=False)',
        'return CatBoostClassifier(iterations=300, depth=6, learning_rate=0.1, random_seed=seed,\n'
        '                                  verbose=False, allow_writing_files=False,\n'
        '                                  thread_count=_train_jobs())')

    if text == before:
        print("train.py: ANCHOR NOT FOUND")
        return 1
    TRAIN.write_text(text, encoding="utf-8")
    print("train.py: EVOVS_TRAIN_JOBS knob added (default 1, behaviour-neutral)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
