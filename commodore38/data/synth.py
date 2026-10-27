"""Build a verified SFT dataset (brief §5): generate, verify, keep only what passes.

For each task from the parametrized families, a teacher model answers with the
skill document as system prompt and gets up to --max-repairs rounds of verifier
feedback (the eval's skills-loop). Only answers that pass the full pipeline
(checker -> build -> VICE -> expected result) are kept. The stored sample uses
the short "bare" system prompt and the clean code block, so the fine-tuned model
learns to behave like the skill-guided model without needing the skill.

  c38-synth --model mtplx-qwen38-27b-optimized-speed --out data/v0.1 \
            --c64-basic 80 --c128-basic 70 --c64-kickass 50

Writes train.jsonl / valid.jsonl ({"messages": [...]}, as mlx_lm.lora expects),
all.jsonl with metadata per sample, and rejected.jsonl.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from collections import Counter
from pathlib import Path

from ..eval.runner import load_tasks, run_task, system_prompt
from ..verify import Expectation, verify_source
from .families import Task, generate_tasks

FENCE_TAG = {"c64-basic": "basic", "c128-basic": "basic", "c64-kickass": "asm"}


def normalize(code: str) -> str:
    return "\n".join(l.strip().lower() for l in code.strip().splitlines() if l.strip())


def make_sample(task, code: str) -> dict:
    return {"messages": [
        {"role": "system", "content": system_prompt(task.language, "bare")},
        {"role": "user", "content": task.prompt},
        {"role": "assistant", "content": f"```{FENCE_TAG[task.language]}\n{code}```"},
    ]}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Generate a verified SFT dataset.")
    p.add_argument("--base-url", default="http://127.0.0.1:8000/v1")
    p.add_argument("--model", default="")
    p.add_argument("--api-key", default="local")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--c64-basic", type=int, default=80)
    p.add_argument("--c128-basic", type=int, default=70)
    p.add_argument("--c64-kickass", type=int, default=50)
    p.add_argument("--seed", type=int, default=38)
    p.add_argument("--valid-fraction", type=float, default=0.1)
    p.add_argument("--max-repairs", type=int, default=3)
    p.add_argument("--temperature", type=float, default=0.4)
    p.add_argument("--max-tokens", type=int, default=4096)
    p.add_argument("--request-timeout", type=float, default=900)
    p.add_argument("--run-timeout", type=float, default=20)
    p.add_argument("--reverify-rejected", action="store_true",
                   help="no generation: re-verify rejected.jsonl in --out and rebuild the splits")
    args = p.parse_args(argv)
    if args.reverify_rejected:
        reverify_rejected(args.out, args.run_timeout)
        write_splits(args.out, args.seed, args.valid_fraction)
        return 0
    if not args.model:
        p.error("--model is required")
    # run_task reads the eval's option names
    args.variant, args.no_think = "skills-loop", True

    tasks = generate_tasks({"c64-basic": args.c64_basic, "c128-basic": args.c128_basic,
                            "c64-kickass": args.c64_kickass}, seed=args.seed)
    # Decontamination: never train on a benchmark prompt or reference solution.
    eval_prompts = {t["prompt"] for t in load_tasks()}
    eval_codes = {normalize(t["reference"]) for t in load_tasks()}
    tasks = [t for t in tasks if t.prompt not in eval_prompts]

    args.out.mkdir(parents=True, exist_ok=True)
    seen_codes = set()
    with (args.out / "all.jsonl").open("w", encoding="utf-8") as all_f, \
         (args.out / "rejected.jsonl").open("w", encoding="utf-8") as rej_f:
        for i, task in enumerate(tasks, 1):
            res = run_task({"id": f"{task.family}-{i}", "language": task.language,
                            "prompt": task.prompt, "expect": task.expect}, args)
            code = res["log"][-1].get("code") if res["log"] else None
            meta = {"family": task.family, "language": task.language, "expect": task.expect,
                    "attempts": res["attempts"], "status": res["status"],
                    "source": f"synthetic:{args.model}+skill+verify"}
            reason = None
            if res["status"] != "verified" or not code:
                reason = res["status"]
            elif normalize(code) in eval_codes:
                reason = "matches_eval_reference"
            elif normalize(code) in seen_codes:
                reason = "duplicate"
            if reason:
                rej_f.write(json.dumps({**meta, "prompt": task.prompt, "reason": reason, "code": code}, ensure_ascii=False) + "\n")
            else:
                seen_codes.add(normalize(code))
                sample = make_sample(task, code)
                sample_id = hashlib.sha256(json.dumps(sample).encode()).hexdigest()[:12]
                all_f.write(json.dumps({"id": sample_id, **sample, "meta": meta}, ensure_ascii=False) + "\n")
            print(f"[{i}/{len(tasks)}] {task.language:<11} {task.family:<15} {reason or 'kept'} (attempts={res['attempts']})", flush=True)

    write_splits(args.out, args.seed, args.valid_fraction)
    return 0


def reverify_rejected(out: Path, run_timeout: float) -> None:
    """Re-run rejected answers through the (fixed) pipeline; move those that now pass."""
    seen = {normalize(json.loads(l)["messages"][-1]["content"].split("\n", 1)[1].rsplit("```", 1)[0])
            for l in (out / "all.jsonl").open(encoding="utf-8")}
    still_rejected, recovered = [], 0
    with (out / "all.jsonl").open("a", encoding="utf-8") as all_f:
        for line in (out / "rejected.jsonl").open(encoding="utf-8"):
            r = json.loads(line)
            code = r.get("code")
            if r["reason"] == "failed" and code and normalize(code) not in seen:
                res = verify_source(code, r["language"], expect=Expectation.from_dict(r["expect"]), timeout=run_timeout)
                if res.status == "verified":
                    task = Task(r["family"], r["language"], r["prompt"], r["expect"])
                    sample = make_sample(task, code)
                    meta = {k: r[k] for k in ("family", "language", "expect", "attempts", "source")}
                    meta.update(status="verified", note="recovered by --reverify-rejected")
                    sample_id = hashlib.sha256(json.dumps(sample).encode()).hexdigest()[:12]
                    all_f.write(json.dumps({"id": sample_id, **sample, "meta": meta}, ensure_ascii=False) + "\n")
                    seen.add(normalize(code))
                    recovered += 1
                    print(f"recovered {r['language']} {r['family']}")
                    continue
            still_rejected.append(line)
    (out / "rejected.jsonl").write_text("".join(still_rejected), encoding="utf-8")
    print(f"{recovered} recovered, {len(still_rejected)} still rejected")


def write_splits(out: Path, seed: int, valid_fraction: float) -> None:
    """(Re)build train.jsonl / valid.jsonl and summary.json from all.jsonl."""
    rows = [json.loads(l) for l in (out / "all.jsonl").open(encoding="utf-8")]
    rejected = [json.loads(l) for l in (out / "rejected.jsonl").open(encoding="utf-8")]
    samples = [{"messages": r["messages"]} for r in sorted(rows, key=lambda r: r["id"])]
    random.Random(seed).shuffle(samples)
    n_valid = max(1, int(len(samples) * valid_fraction))
    for name, part in (("valid", samples[:n_valid]), ("train", samples[n_valid:])):
        with (out / f"{name}.jsonl").open("w", encoding="utf-8") as f:
            for s in part:
                f.write(json.dumps(s, ensure_ascii=False) + "\n")

    stats = Counter((r["meta"]["language"], "kept") for r in rows)
    stats.update((r["language"], r["reason"]) for r in rejected)
    summary = {f"{lang}/{what}": n for (lang, what), n in sorted(stats.items())}
    summary.update(train=len(samples) - n_valid, valid=n_valid)
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    sys.exit(main())
