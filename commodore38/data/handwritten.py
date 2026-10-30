"""Hand-written training samples for tasks the teacher model could not solve.

The synthetic teacher (Qwen3.8-27B + skill + checker loop) fails some families
outright: lcm (no gcd() in BASIC V2), Collatz loops, binary strings (str$ adds a
space), screen codes vs PETSCII, several 6502 routines. Those tasks are exported
here, solved by hand (in v0.4 by Claude in the coding session), and every
solution goes through exactly the same pipeline as synthetic samples: checker ->
build -> VICE -> expected screen/memory. Only verified programs become samples.

  python -m commodore38.data.handwritten export --out data/v0.4-claude
  # write data/v0.4-claude/solutions/<task id>.bas (or .asm) for each task
  python -m commodore38.data.handwritten verify --out data/v0.4-claude [--only id ...]

`verify` rebuilds all.jsonl / rejected.jsonl / train / valid from the solution
files every time, so it can be re-run after fixing solutions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from ..config import REPO_ROOT
from ..eval.runner import load_tasks
from ..verify import Expectation, verify_source
from .families import Task
from .synth import make_sample, normalize, write_splits

# v0.3 and older clear_print rejects used a row-0 check that wrongly failed correct code.
SKIP_FAMILIES = {"clear_print"}
SOURCE = "handwritten:claude-opus-5.5+verify"


def export(out: Path) -> None:
    seen, tasks = set(), []
    for path in sorted((REPO_ROOT / "data").glob("*/rejected.jsonl")):
        for line in path.open(encoding="utf-8"):
            r = json.loads(line)
            if r["family"] in SKIP_FAMILIES or r["prompt"] in seen:
                continue
            seen.add(r["prompt"])
            task_id = f"{r['language']}-{r['family']}-{hashlib.sha256(r['prompt'].encode()).hexdigest()[:6]}"
            tasks.append({"id": task_id, "language": r["language"], "family": r["family"],
                          "prompt": r["prompt"], "expect": r["expect"]})
    tasks.sort(key=lambda t: t["id"])
    out.mkdir(parents=True, exist_ok=True)
    (out / "solutions").mkdir(exist_ok=True)
    with (out / "tasks.jsonl").open("w", encoding="utf-8") as f:
        for t in tasks:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")
    print(f"{len(tasks)} tasks -> {out / 'tasks.jsonl'}")


def solution_path(out: Path, task: dict) -> Path:
    return out / "solutions" / (task["id"] + (".asm" if task["language"].endswith("kickass") else ".bas"))


def verify(out: Path, only: set[str] | None, run_timeout: float, seed: int, valid_fraction: float) -> int:
    tasks = [json.loads(l) for l in (out / "tasks.jsonl").open(encoding="utf-8")]
    eval_codes = {normalize(t["reference"]) for t in load_tasks()}
    previous = {}
    if only and (out / "results.json").exists():
        previous = json.loads((out / "results.json").read_text())
    results, seen_codes = {}, set()
    with (out / "all.jsonl").open("w", encoding="utf-8") as all_f, \
         (out / "rejected.jsonl").open("w", encoding="utf-8") as rej_f:
        for t in tasks:
            path = solution_path(out, t)
            if not path.exists():
                continue
            code = path.read_text(encoding="utf-8")
            code = code if code.endswith("\n") else code + "\n"
            if only is None or t["id"] in only or t["id"] not in previous:
                res = verify_source(code, t["language"], expect=Expectation.from_dict(t["expect"]), timeout=run_timeout)
                status, feedback = res.status, ("" if res.status == "verified" else res.feedback())
            else:
                status, feedback = previous[t["id"]]["status"], previous[t["id"]]["feedback"]
            reason = None if status == "verified" else status
            if not reason and normalize(code) in eval_codes:
                reason = "matches_eval_reference"
            elif not reason and normalize(code) in seen_codes:
                reason = "duplicate"
            meta = {"family": t["family"], "language": t["language"], "expect": t["expect"],
                    "attempts": 1, "status": status, "source": SOURCE}
            if reason:
                rej_f.write(json.dumps({**meta, "prompt": t["prompt"], "reason": reason, "code": code}, ensure_ascii=False) + "\n")
                print(f"FAIL {t['id']}: {reason} {feedback[:300]}")
            else:
                seen_codes.add(normalize(code))
                sample = make_sample(Task(t["family"], t["language"], t["prompt"], t["expect"]), code)
                sample_id = hashlib.sha256(json.dumps(sample).encode()).hexdigest()[:12]
                all_f.write(json.dumps({"id": sample_id, **sample, "meta": meta}, ensure_ascii=False) + "\n")
            results[t["id"]] = {"status": status, "feedback": feedback}
    (out / "results.json").write_text(json.dumps(results, indent=1))
    kept = sum(r["status"] == "verified" for r in results.values())
    print(f"{kept}/{len(results)} solutions verified ({len(tasks)} tasks)")
    write_splits(out, seed, valid_fraction)
    return 0


def check(out: Path, ids: list[str], run_timeout: float) -> int:
    """Verify some solutions and print the result; writes nothing (safe to run in parallel)."""
    tasks = {json.loads(l)["id"]: json.loads(l) for l in (out / "tasks.jsonl").open(encoding="utf-8")}
    bad = 0
    for task_id in ids:
        t = tasks[task_id]
        path = solution_path(out, t)
        if not path.exists():
            print(f"MISSING {task_id}")
            bad += 1
            continue
        res = verify_source(path.read_text(encoding="utf-8"), t["language"],
                            expect=Expectation.from_dict(t["expect"]), timeout=run_timeout)
        print(f"{'OK  ' if res.status == 'verified' else 'FAIL'} {task_id}"
              + ("" if res.status == "verified" else f"\n     {res.feedback()[:700]}"))
        bad += res.status != "verified"
    print(f"{len(ids) - bad}/{len(ids)} verified")
    return 1 if bad else 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Export teacher-failed tasks and verify hand-written solutions.")
    p.add_argument("command", choices=["export", "verify", "check"])
    p.add_argument("ids", nargs="*", help="check: task ids")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--only", nargs="*", help="verify: re-run only these task ids (others keep their last result)")
    p.add_argument("--run-timeout", type=float, default=20)
    p.add_argument("--seed", type=int, default=38)
    p.add_argument("--valid-fraction", type=float, default=0.1)
    args = p.parse_args(argv)
    if args.command == "export":
        export(args.out)
        return 0
    if args.command == "check":
        return check(args.out, args.ids, args.run_timeout)
    return verify(args.out, set(args.only) if args.only else None, args.run_timeout, args.seed, args.valid_fraction)


if __name__ == "__main__":
    sys.exit(main())
