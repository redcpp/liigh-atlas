"""CLI: python -m atlas_pipeline {run,data,tiers,repro,make-fixture} ..."""

from __future__ import annotations

import argparse
import sys
import warnings

from .env import DataRootError, raw_dir


def main(argv: list[str] | None = None) -> int:
    # numpy 2 on macOS Accelerate emits spurious "... encountered in matmul" RuntimeWarnings on finite
    # inputs; outputs are checked for finiteness where it matters (UMAP, contract validation).
    warnings.filterwarnings("ignore", message=".*encountered in matmul", category=RuntimeWarning)
    p = argparse.ArgumentParser(prog="atlas_pipeline")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="run the pipeline for a dataset")
    r.add_argument("dataset")
    d = sub.add_parser("data", help="verify raw tiers (make data)")
    d.add_argument("--tier", default="meta,core,he")
    rp = sub.add_parser("repro", help="run twice and compare asset hashes")
    rp.add_argument("dataset")
    sub.add_parser("make-fixture", help="rebuild fixtures/fixture from ovarian-10x")
    args = p.parse_args(argv)
    try:
        if args.cmd == "data":
            from . import verify

            if args.tier == "list":
                print(verify.render_tiers())
                return 0
            checks = verify.verify(raw_dir("ovarian-10x"), [t.strip() for t in args.tier.split(",") if t.strip()])
            print(verify.render(checks))
            return 0 if all(c.status in ("ok", "downloaded") for c in checks) else 1
        if args.cmd == "run":
            from .run import run

            print(run(args.dataset).render())
            return 0
        if args.cmd == "repro":
            from .run import repro

            ok, text = repro(args.dataset)
            print(text)
            return 0 if ok else 1
        if args.cmd == "make-fixture":
            from .make_fixture import make

            print(make())
            return 0
    except DataRootError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3
    return 2  # pragma: no cover


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
