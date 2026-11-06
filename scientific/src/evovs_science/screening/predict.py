"""Score a molecular library with a fitted pipeline and rank it (Blueprint §9.6).

The library is **unlabeled**: scores are model outputs, so the report records
predictions as predictions and never emits a hit rate or EF for the library
(T-018). Full ranked output plus a top-K file are written with a sha256 manifest.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import time

import numpy as np

from ..chemistry.featurize import featurize, read_smiles, resolve_input_path
from ..manifest import describe_input, sha256_file, utc_now, write_manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evovs-science rank")
    parser.add_argument("--model", required=True, help="fitted pipeline from modeling.train")
    parser.add_argument("--library", required=True, help="SMILES library (.smi/.csv)")
    parser.add_argument("--output", required=True, help="ranked CSV, best first, one row per featurized molecule")
    parser.add_argument("--top-output", required=True, help="top-K CSV")
    parser.add_argument("--report", required=True, help="screening report json")
    parser.add_argument("--top-k", type=int, default=100)
    parser.add_argument("--radius", type=int, default=2, help="must match the model's training featurization")
    parser.add_argument("--n-bits", type=int, default=2048)
    parser.add_argument("--id-column", default="id")
    parser.add_argument("--smiles-column", default="smiles")
    args = parser.parse_args(argv)

    import joblib

    started = time.time()
    if not os.path.isfile(args.model):
        # The corpus failure: an agent passed `does_not_exist.pkl`. Say which fitted
        # pipelines do exist instead of only refusing the one that does not.
        import glob
        here = glob.glob(os.path.join(os.getcwd(), "runs", "models", "*", "model.joblib"))
        raise SystemExit(f"--model must be the fitted pipeline FILE from modeling.train "
                         f"(e.g. runs/models/<name>/model.joblib); got {args.model}"
                         + (f"; fitted pipelines here: {here[:3]}" if here else ""))
    library_path = resolve_input_path(args.library)  # the manifest hashes the real file
    rows = read_smiles(library_path, None, args.id_column, args.smiles_column)
    ids, matrix, descriptors, invalid = featurize(rows, radius=args.radius, n_bits=args.n_bits)
    if not ids:
        raise SystemExit("no library molecule could be featurized")

    features = np.hstack([matrix.astype(np.float32), descriptors]).astype(np.float32)
    model = joblib.load(args.model)
    scores = model.predict_proba(features)[:, 1]

    order = np.argsort(-scores)
    smiles_of = {}
    for (molecule_id, smiles), kept_id in zip(rows, ids):
        smiles_of[kept_id] = smiles

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    ranked_path = os.path.abspath(args.output)
    with open(ranked_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["rank", "id", "smiles", "score"])
        for position, index in enumerate(order, 1):
            writer.writerow([position, ids[index], smiles_of.get(ids[index], ""), f"{scores[index]:.6f}"])

    top_k = min(args.top_k, len(order))
    top_path = os.path.abspath(args.top_output)
    with open(top_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["rank", "id", "smiles", "score"])
        for position in range(top_k):
            index = int(order[position])
            writer.writerow([position + 1, ids[index], smiles_of.get(ids[index], ""), f"{scores[index]:.6f}"])

    top_scores = [float(scores[int(order[position])]) for position in range(top_k)]
    report = {
        "schema_version": "1",
        "created_at": utc_now(),
        "library": os.path.basename(args.library),
        "rows_read": len(rows),
        "rows_featurized": len(ids),
        "rows_invalid": len(invalid),
        "invalid": invalid[:100],
        "duplicates_note": "the library is scored as provided; deduplication is the caller's preprocessing step",
        "parameters": {"radius": args.radius, "n_bits": args.n_bits, "top_k": top_k},
        "model_sha256": sha256_file(args.model),
        "library_sha256": sha256_file(library_path),
        "elapsed_seconds": round(time.time() - started, 1),
        "predictions_are": "model scores on an unlabeled library; no hit rate or enrichment is defined here",
        "top_score_range": [min(top_scores), max(top_scores)] if top_scores else None,
    }
    with open(args.report, "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    write_manifest(
        os.path.dirname(ranked_path),
        [
            {"path": ranked_path, "content_type": "text/csv", "description": "full ranked library"},
            {"path": top_path, "content_type": "text/csv", "description": f"top {top_k} candidates"},
            {"path": args.report, "content_type": "application/json", "description": "screening report"},
        ],
        generator="evovs_science.screening.predict",
        inputs=[describe_input(library_path)],
        parameters={"radius": args.radius, "n_bits": args.n_bits, "top_k": top_k},
        extra={"model_sha256": report["model_sha256"]},
    )

    print(json.dumps({"rows_read": len(rows), "featurized": len(ids), "invalid": len(invalid),
                      "top_k": top_k, "output": args.output, "elapsed": report["elapsed_seconds"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
