#!/usr/bin/env python3
"""Wire the frozen search space into `ml.train`.

Adds three arguments:
  --config-id     draw one configuration from evovs_science.search.space and
                  charge it against this ticket's budget (refused when exhausted)
  --workspace     where the budget ledger lives (defaults to the cwd = ticket dir)
  --budget-limit  the budget for this ticket (default 100 = the whole space)

Without --config-id the tool behaves exactly as before, so existing agents and the
old records keep working. With it, the model/seed must agree with the named
configuration: the point is to make "search within a bounded space" enforceable,
not to let an arm declare a config and train something else.
"""
from pathlib import Path

TRAIN = Path("/home/linhan_cluster/evo_vs_rsi/scientific/src/evovs_science/modeling/train.py")

OLD_ARGS = '''    parser.add_argument("--label-column", default="label")
    args = parser.parse_args(argv)'''

NEW_ARGS = '''    parser.add_argument("--label-column", default="label")
    parser.add_argument("--config-id", default=None,
                        help="configuration id from the frozen search space; charges the budget")
    parser.add_argument("--workspace", default=".",
                        help="ticket directory holding .search_budget.json")
    parser.add_argument("--budget-limit", type=int, default=None,
                        help="how many configurations this ticket may draw (default: the whole space)")
    args = parser.parse_args(argv)

    if args.config_id:
        # Import here so the tool keeps working without the search package installed.
        from ..search.budget import consume, read
        from ..search.space import LIMIT_TOTAL, get as get_config

        config = get_config(args.config_id)
        if config.model != args.model:
            raise SystemExit(f"config {config.id} declares model={config.model}, "
                             f"but --model={args.model}; the configuration is the unit of search")
        if config.seed != args.seed:
            raise SystemExit(f"config {config.id} declares seed={config.seed}, "
                             f"but --seed={args.seed}")
        limit = args.budget_limit if args.budget_limit is not None else LIMIT_TOTAL
        state = consume(args.workspace, config.id, limit)
        print(f"search draw {state['used']}/{state['limit']} -> {config.id}", flush=True)'''

OLD_TAIL = '''    return 0


if __name__ == "__main__":'''
NEW_TAIL = '''    if args.config_id:
        # Leave a per-step copy so a record can show which draw produced it even
        # when the ticket ledger is later rotated.
        import json as _json
        from ..search.budget import read as _read
        snapshot = _read(args.workspace)
        out = Path(args.output_dir)
        if out.exists():
            (out / "search_draw.json").write_text(
                _json.dumps({"config_id": args.config_id, **snapshot}, ensure_ascii=False, indent=2) + "\\n",
                encoding="utf-8")
    return 0


if __name__ == "__main__":'''


def main() -> int:
    text = TRAIN.read_text(encoding="utf-8")
    if "--config-id" in text:
        print("train.py: already wired")
        return 0
    before = text
    text = text.replace(OLD_ARGS, NEW_ARGS)
    text = text.replace(OLD_TAIL, NEW_TAIL)
    if text == before:
        print("train.py: ANCHOR NOT FOUND")
        return 1
    TRAIN.write_text(text, encoding="utf-8")
    print("train.py: --config-id / --workspace / --budget-limit wired")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
