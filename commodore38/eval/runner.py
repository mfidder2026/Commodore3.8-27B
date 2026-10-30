"""Commodore-Eval runner (brief §7).

Sends each benchmark task to an OpenAI-compatible chat endpoint, extracts the
code block from the answer and runs it through the verification pipeline.

Variants:
  bare         short system prompt, one attempt
  skills       skill document as system prompt, one attempt
  skills-loop  skill document + up to --max-repairs rounds of verifier feedback
  bare-loop    short system prompt + repair rounds (what c38-write does)

  c38-eval --base-url http://127.0.0.1:8000/v1 --model <id> --variant skills-loop
  c38-eval --references          # check that every task's reference solution verifies
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from ..config import REPO_ROOT, load_toolchain
from ..verify import Expectation, verify_source

TASKS_DIR = Path(__file__).parent / "tasks"

# language -> skill document, relative to the external dir
SKILLS = {
    "c64-basic": "c64_basic_ai_skillset/c64_basic_skill.md",
    "c128-basic": "c128_basic_ai_skillset/c128_basic_skill.md",
    "c64-kickass": "c64_kickass_ai_skillset/C64_KICKASS_SKILL.md",
}

OUTPUT_CONTRACT = {
    "basic": (
        "Answer with exactly one fenced code block containing the complete program. "
        "Use lowercase source with line numbers. Write PETSCII control codes as chr$(n), "
        "for example print chr$(147) to clear the screen."
    ),
    "asm": (
        "Answer with exactly one fenced code block containing the complete Kick Assembler "
        "source, assemblable on its own."
    ),
}

_CODE_BLOCK = re.compile(r"```[^\n`]*\n(.*?)```", re.DOTALL)
_THINK = re.compile(r"<think>.*?</think>", re.DOTALL)


def load_tasks(languages: list[str] | None = None) -> list[dict]:
    tasks = []
    for path in sorted(TASKS_DIR.glob("*.json")):
        tasks.extend(json.loads(path.read_text(encoding="utf-8")))
    return [t for t in tasks if not languages or t["language"] in languages]


def extract_code(answer: str) -> str | None:
    answer = _THINK.sub("", answer)
    blocks = _CODE_BLOCK.findall(answer)
    if not blocks:
        return None
    code = max(blocks, key=len)  # the program, not a one-line usage example
    return code if code.endswith("\n") else code + "\n"


def system_prompt(language: str, variant: str) -> str:
    kind = "asm" if language.endswith("kickass") else "basic"
    base = f"You are an expert Commodore programmer. {OUTPUT_CONTRACT[kind]}"
    if variant in ("bare", "bare-loop"):
        return base
    skill = load_toolchain().external_dir / SKILLS[language]
    return f"{base}\n\nFollow this skill document strictly:\n\n{skill.read_text(encoding='utf-8')}"


def chat(base_url: str, model: str, messages: list[dict], args) -> tuple[str, dict]:
    body = {"model": model, "messages": messages, "temperature": args.temperature, "max_tokens": args.max_tokens}
    if args.no_think:
        body["chat_template_kwargs"] = {"enable_thinking": False}
    req = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {args.api_key}"},
    )
    with urllib.request.urlopen(req, timeout=args.request_timeout) as resp:
        data = json.load(resp)
    return data["choices"][0]["message"].get("content") or "", data.get("usage", {})


def run_task(task: dict, args) -> dict:
    expect = Expectation.from_dict(task.get("expect"))
    messages = [
        {"role": "system", "content": system_prompt(task["language"], args.variant)},
        {"role": "user", "content": task["prompt"]},
    ]
    max_attempts = 1 + (args.max_repairs if args.variant.endswith("-loop") else 0)
    attempts = []
    for attempt in range(max_attempts):
        t0 = time.monotonic()
        try:
            answer, usage = chat(args.base_url, args.model, messages, args)
        except (urllib.error.URLError, TimeoutError, KeyError) as exc:
            attempts.append({"error": f"request failed: {exc}"})
            break
        gen_seconds = time.monotonic() - t0
        code = extract_code(answer)
        rec = {"seconds": round(gen_seconds, 1), "usage": usage, "code": code}
        if code is None:
            rec.update(status="no_code", answer=answer[-2000:])
            feedback = "Your answer did not contain a fenced code block. Reply with the complete program in one code block."
        else:
            res = verify_source(code, task["language"], expect=expect, timeout=args.run_timeout)
            rec.update(status=res.status, verify=res.to_dict())
            if res.status != "failed":
                attempts.append(rec)
                break
            feedback = f"The verifier rejected the program.\n{res.feedback()}\nFix it and reply with the complete corrected program."
        attempts.append(rec)
        messages += [{"role": "assistant", "content": answer}, {"role": "user", "content": feedback}]

    final = attempts[-1] if attempts else {}
    stages = {s["name"]: s["status"] for s in final.get("verify", {}).get("stages", [])}

    # Lenient score: classic all-uppercase BASIC listings break the lowercase + bas2prg -i
    # convention (D2) but are otherwise fine. Re-verify the first attempt in lowercase so
    # convention errors and logic errors can be told apart in the report.
    first = attempts[0] if attempts else {}
    lenient = first.get("status", "error")
    code = first.get("code")
    if lenient == "failed" and code and task["language"].endswith("basic") and code == code.upper():
        lenient = verify_source(code.lower(), task["language"], expect=expect, timeout=args.run_timeout).status
    return {
        "id": task["id"],
        "language": task["language"],
        "status": final.get("status", "error"),
        "check_clean": stages.get("check") == "passed",
        "built": stages.get("build") == "passed",
        "attempts": len(attempts),
        "first_attempt_status": first.get("status", "error"),
        "first_attempt_lenient_status": lenient,
        "log": attempts,
    }


def summarize(results: list[dict]) -> dict:
    by_lang: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        by_lang[r["language"]].append(r)
    by_lang["ALL"] = results
    summary = {}
    for lang, rs in by_lang.items():
        n = len(rs)
        summary[lang] = {
            "tasks": n,
            "check_clean": sum(r["check_clean"] for r in rs) / n,
            "built": sum(r["built"] for r in rs) / n,
            "pass@1_first_attempt": sum(r["first_attempt_status"] == "verified" for r in rs) / n,
            "pass@1_lenient_case": sum(r["first_attempt_lenient_status"] == "verified" for r in rs) / n,
            "pass_final": sum(r["status"] == "verified" for r in rs) / n,
            "incomplete": sum(r["status"] == "incomplete" for r in rs),
        }
    return summary


def check_references(tasks: list[dict], timeout: float) -> int:
    bad = 0
    for t in tasks:
        res = verify_source(t["reference"], t["language"], expect=Expectation.from_dict(t.get("expect")), timeout=timeout)
        print(f"{t['id']:<22} {res.status}")
        if res.status == "failed":
            bad += 1
            print("    " + res.feedback()[:600])
    print(f"{bad} reference(s) failed")
    return 1 if bad else 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Run Commodore-Eval against an OpenAI-compatible endpoint.")
    p.add_argument("--base-url", default="http://127.0.0.1:8000/v1")
    p.add_argument("--model", default="")
    p.add_argument("--api-key", default="local")
    p.add_argument("--variant", choices=["bare", "bare-loop", "skills", "skills-loop"], default="bare")
    p.add_argument("--lang", action="append", help="only these languages (repeatable)")
    p.add_argument("--task", action="append", help="only these task ids (repeatable)")
    p.add_argument("--max-repairs", type=int, default=3)
    p.add_argument("--temperature", type=float, default=0.2)
    p.add_argument("--max-tokens", type=int, default=4096)
    p.add_argument("--no-think", action="store_true", help="ask the chat template to disable thinking")
    p.add_argument("--request-timeout", type=float, default=900)
    p.add_argument("--run-timeout", type=float, default=20)
    p.add_argument("--out", type=Path, default=REPO_ROOT / "runs")
    p.add_argument("--references", action="store_true", help="verify the reference solutions instead of a model")
    args = p.parse_args(argv)

    tasks = load_tasks(args.lang)
    if args.task:
        tasks = [t for t in tasks if t["id"] in args.task]
    if args.references:
        return check_references(tasks, args.run_timeout)
    if not args.model:
        p.error("--model is required")

    run_dir = args.out / f"{datetime.now():%Y%m%d-%H%M%S}-{args.variant}"
    run_dir.mkdir(parents=True, exist_ok=True)
    meta = {k: (str(v) if isinstance(v, Path) else v) for k, v in vars(args).items()}
    (run_dir / "config.json").write_text(json.dumps(meta, indent=2))

    results = []
    with (run_dir / "results.jsonl").open("w", encoding="utf-8") as out:
        for i, task in enumerate(tasks, 1):
            r = run_task(task, args)
            results.append(r)
            out.write(json.dumps(r, ensure_ascii=False) + "\n")
            out.flush()
            print(f"[{i}/{len(tasks)}] {task['id']:<22} {r['status']:<10} attempts={r['attempts']}", flush=True)

    summary = summarize(results)
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    print(f"results: {run_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
