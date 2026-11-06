import argparse
import re
import time


def identifier(value):
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}", value):
        raise argparse.ArgumentTypeError("Use 1-80 ASCII letters/digits/_/-")
    return value


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("migrate")
    sub.add_parser("import-food")
    catalog = sub.add_parser("enrich-catalog")
    catalog.add_argument("--apply", action="store_true")
    catalog.add_argument("--backup")
    w = sub.add_parser("sync")
    mode = w.add_mutually_exclusive_group()
    mode.add_argument("--loop", action="store_true")
    mode.add_argument("--drain", action="store_true")
    t = sub.add_parser("train")
    t.add_argument("--run-id", required=True, type=identifier)
    t.add_argument("--seeds", type=int, default=10)
    t.add_argument("--epochs", type=int, default=50)
    t.add_argument("--dimension", type=int, default=128)
    t.add_argument("--minsup", type=float, default=0.006)
    a = sub.add_parser("activate")
    a.add_argument("--run-id", required=True, type=identifier)
    a.add_argument("--seed", type=int, default=0)
    b = sub.add_parser("benchmark")
    b.add_argument("--training-run", required=True, type=identifier)
    b.add_argument("--run-id", required=True, type=identifier)
    b.add_argument("--seed", type=int, default=0)
    b.add_argument("--reuse-data-run", type=identifier)
    b.add_argument("--repeats", type=int, default=5)
    b.add_argument("--warmup", type=int, default=50)
    pub = sub.add_parser("publish")
    pub.add_argument("--run-id", required=True, type=identifier)
    args = p.parse_args()
    if args.cmd == "migrate":
        from .schema import migrate

        migrate()
    elif args.cmd == "import-food":
        from .ingest import import_food

        import_food()
    elif args.cmd == "enrich-catalog":
        from .catalog import enrich
        from .db import session

        with session() as db:
            print(enrich(db, apply=args.apply, backup=args.backup))
    elif args.cmd == "train":
        if (
            args.seeds < 1
            or args.epochs < 1
            or args.dimension < 2
            or not 0 < args.minsup <= 1
        ):
            p.error("Invalid training parameters")
        from .pipeline import train

        train(
            args.run_id,
            seeds=range(args.seeds),
            dim=args.dimension,
            epochs=args.epochs,
            minsup=args.minsup,
        )
    elif args.cmd == "activate":
        from .vector import activate

        activate(args.run_id, args.seed)
    elif args.cmd == "benchmark":
        if args.repeats < 1 or args.warmup < 1:
            p.error("repeats/warmup must be positive")
        from .benchmark import run

        run(
            args.training_run,
            args.run_id,
            args.seed,
            repeats=args.repeats,
            warmup=args.warmup,
            reuse_data_run=args.reuse_data_run,
        )
    elif args.cmd == "publish":
        from .vector import publish

        publish(args.run_id)
    elif args.cmd == "sync":
        from .vector import sync_once

        while True:
            try:
                count = sync_once()
                print("Synchronized", count, flush=True)
            except Exception:
                import logging

                logging.exception("Sync iteration failed")
                if not args.loop:
                    raise
            if args.drain and count:
                continue
            if not args.loop:
                break
            time.sleep(5)


if __name__ == "__main__":
    main()
