"""The frozen search space every arm is allowed to explore.

Why this exists
---------------
Before this module each arm decided for itself how many models to train: one arm
trained 13, another 5, another 7. Comparing them on "best validation AUROC" then
measured *how many draws were taken*, not how well the arm searched — `max()` over
N models rises with N regardless of skill.

So the space is frozen here, identical for all four arms, and the tool layer
refuses any configuration outside it. Efficiency then means "reached a given
quality with fewer draws", which is the comparison the experiment is for.

Layout: 4 algorithms x 5 feature representations x 5 seeds = 100 configurations.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass

SPACE_VERSION = "p8-100-v2"

ALGORITHMS = ("logreg", "rf", "xgboost", "catboost")

# Five feature representations, each expressed with the arguments `rdkit.featurize`
# actually accepts (--desc-set is limited to v1|v2; radius 1-4, n_bits 256-4096).
# A space the tools cannot execute is not a search space, so the combinations are
# spelled out here rather than named loosely.
FEATURE_SPECS = {
    "v1":     {"desc_set": "v1", "radius": 2, "n_bits": 2048},
    "v2":     {"desc_set": "v2", "radius": 3, "n_bits": 2048},
    "r1":     {"desc_set": "v1", "radius": 1, "n_bits": 2048},
    "b4096":  {"desc_set": "v1", "radius": 2, "n_bits": 4096},
    "r3b4096": {"desc_set": "v2", "radius": 3, "n_bits": 4096},
}
FEATURE_SETS = tuple(FEATURE_SPECS)
SEEDS = (17, 23, 42, 7, 101)

LIMIT_TOTAL = len(ALGORITHMS) * len(FEATURE_SETS) * len(SEEDS)   # 100


@dataclass(frozen=True)
class Config:
    """One point of the search space. The id is stable across rounds."""

    id: str
    model: str
    desc_set: str
    seed: int

    def as_dict(self) -> dict:
        return asdict(self)


def _build() -> tuple[Config, ...]:
    """Order matters: a small budget must still buy diversity.

    Algorithm-major ordering means the first twenty points are twenty logreg seeds,
    so at budget 4 the baseline would only ever see one algorithm and the budget
    sweep would measure that accident rather than the search. Seeds are therefore
    the outermost loop: every (algorithm, feature set) pair appears once before any
    seed repeats, so budget 4 covers the four model families and budget 20 covers
    all twenty representation/algorithm combinations.
    """
    configs = []
    for seed in SEEDS:
        for features in FEATURE_SETS:
            for algorithm in ALGORITHMS:
                configs.append(Config(id=f"{algorithm}-{features}-s{seed}",
                                      model=algorithm, desc_set=features, seed=seed))
    return tuple(configs)


CONFIGS: tuple[Config, ...] = _build()
BY_ID: dict[str, Config] = {item.id: item for item in CONFIGS}
assert len(CONFIGS) == LIMIT_TOTAL == 100, len(CONFIGS)


def fingerprint() -> str:
    """Stable digest of the space, so a record proves which space it was run on."""
    payload = json.dumps([[c.id, c.model, c.desc_set, c.seed] for c in CONFIGS],
                         sort_keys=True).encode()
    return hashlib.sha256(payload).hexdigest()[:16]


def get(config_id: str) -> Config:
    """Resolve an id, or a plain index into the ordered space.

    Accepting the index is not sugar: the first agent run passed `000`/`001` (it read
    the listing as a numbered table), the tool rejected them, and two attempts were
    spent discovering that ids are strings like `rf-v1-s17`. An index of the same
    space is unambiguous, so it is accepted and resolved here.
    """
    key = str(config_id).strip().lstrip("#")
    # Accept an index, optionally decorated (`000`, `cfg000`, `config_7`). The first
    # agent run invented `cfg000`, so treating the trailing digits as an index keeps
    # a formatting guess from burning a draw. Anything without digits is matched as
    # an id, and the error below teaches the format instead of only refusing.
    digits = "".join(ch for ch in key if ch.isdigit()) if any(ch.isdigit() for ch in key) else ""
    stripped = "".join(ch for ch in key if not ch.isdigit()).lower()
    if digits and stripped in ("", "cfg", "config", "c", "id", "-", "_", "#"):
        index = int(digits)
        if 0 <= index < len(CONFIGS):
            return CONFIGS[index]
        raise SystemExit(f"configuration index {index} is out of range; the space has "
                         f"{len(CONFIGS)} entries numbered 0..{len(CONFIGS) - 1}")
    if key in BY_ID:
        return BY_ID[key]
    sample = ", ".join(c.id for c in CONFIGS[:6])
    raise SystemExit(
        f"unknown configuration '{config_id}'. Ids look like `rf-v1-s17`; you may also pass "
        f"the index 0..{len(CONFIGS) - 1}. First entries: {sample}. "
        f"List the whole space with `search.space`.")


def as_json() -> dict:
    return {
        "space_version": SPACE_VERSION,
        "fingerprint": fingerprint(),
        "total": len(CONFIGS),
        "algorithms": list(ALGORITHMS),
        "feature_sets": [{"id": key, **FEATURE_SPECS[key]} for key in FEATURE_SETS],
        "seeds": list(SEEDS),
        "configs": [c.as_dict() for c in CONFIGS],
    }


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(prog="evovs_science.search.space")
    parser.add_argument("--list", action="store_true", help="print the frozen space")
    parser.add_argument("--json", action="store_true", help="full JSON instead of the compact table")
    args = parser.parse_args(argv)
    if not args.list:
        parser.error("give --list")
    if args.json:
        print(json.dumps(as_json(), ensure_ascii=False, indent=2))
        return 0
    # Compact by default: 100 identical JSON objects is a lot of context for an agent
    # that only needs (index, id) to make a draw.
    print(f"# space {SPACE_VERSION} fingerprint {fingerprint()} total {len(CONFIGS)}")
    print("# idx\tid\tmodel\tfeatures\tseed")
    for index, config in enumerate(CONFIGS):
        print(f"{index}\t{config.id}\t{config.model}\t{config.desc_set}\t{config.seed}")
    print("# draw with ml.train --config-id <id> (or --config-id <idx>); "
          "each new id costs one draw")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
