"""Write a Commodore program with the local model and only hand back code that works.

The model answers, the program goes through the full pipeline (checker -> build ->
VICE), and on failure the verifier's report goes back to the model, up to
--max-repairs times: the eval's repair loop, as a tool. The fine-tuned model was
trained on the short "bare" system prompt, so that is what it gets here too.

  c38-write "a program that clears the screen and prints HELLO in yellow"
  c38-write "countdown from 10 to 1" --expect " 1" -o countdown.bas
  c38-write "sum the numbers 1 to 100 in c128 basic"          # language is guessed
  c38-write "fill the screen with hearts" --lang c64-kickass --prg hearts.prg

Without --expect the loop catches syntax errors, build errors and crashes, not
programs that run but do the wrong thing. Programs that keep running (games, key
loops) are accepted after --run-timeout seconds unless --must-finish is given.
Exit code 0 only for a verified program.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
import time
import urllib.error
from pathlib import Path

from .build import build
from .eval.runner import chat, extract_code, system_prompt
from .verify import Expectation, verify_source

DIALECT = {
    "c64-basic": "C64 BASIC V2",
    "c128-basic": "C128 BASIC 7.0",
    "c64-kickass": "Kick Assembler program for the C64 with a BASIC upstart",
}


def guess_language(prompt: str) -> str:
    p = prompt.lower()
    if any(k in p for k in ("kick", "assembler", "assembly", "6502", " asm")):
        return "c64-kickass"
    if "c128" in p or "basic 7" in p:
        return "c128-basic"
    return "c64-basic"


def full_prompt(prompt: str, language: str) -> str:
    # Training prompts always name the dialect ("Write a C64 BASIC V2 program that ...").
    if any(k in prompt.lower() for k in ("c64", "c128", "kick assembler", "basic v2", "basic 7")):
        return prompt
    article = "a"
    return f"Write {article} {DIALECT[language]} {'' if language.endswith('kickass') else 'program '}that does the following: {prompt}"


def write_program(prompt: str, language: str, args, log=print) -> tuple[str | None, object]:
    """Returns (code, last VerifyResult); code is None if no attempt produced any."""
    expect = Expectation(args.expect, allow_timeout=not args.must_finish)
    messages = [
        {"role": "system", "content": system_prompt(language, "bare")},
        {"role": "user", "content": full_prompt(prompt, language)},
    ]
    code, res = None, None
    for attempt in range(1, args.max_repairs + 2):
        t0 = time.monotonic()
        answer, _ = chat(args.base_url, args.model, messages, args)
        new = extract_code(answer)
        if new is None:
            log(f"attempt {attempt}: no code block")
            feedback = "Your answer did not contain a fenced code block. Reply with the complete program in one code block."
        else:
            code = new
            res = verify_source(code, language, expect=expect, timeout=args.run_timeout)
            log(f"attempt {attempt}: {res.status} ({time.monotonic() - t0:.1f}s)"
                + ("" if res.status == "verified" else f" - {res.feedback()[:160]}"))
            if res.status != "failed":
                return code, res
            feedback = f"The verifier rejected the program.\n{res.feedback()}\nFix it and reply with the complete corrected program."
        messages += [{"role": "assistant", "content": answer}, {"role": "user", "content": feedback}]
    return code, res


def save_prg(code: str, language: str, dest: Path) -> bool:
    with tempfile.TemporaryDirectory(prefix="c38-write-") as tmp:
        src = Path(tmp) / ("program.asm" if language.endswith("kickass") else "program.bas")
        src.write_text(code, encoding="utf-8")
        built = build(src, language, Path(tmp))
        if not built.ok:
            return False
        shutil.copy(built.prg, dest)
    return True


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Write a verified Commodore program with the local model.")
    p.add_argument("prompt", help="what the program should do")
    p.add_argument("--lang", choices=sorted(DIALECT), help="default: guessed from the prompt, else c64-basic")
    p.add_argument("--expect", action="append", default=[], help="text the program must print (repeatable)")
    p.add_argument("--must-finish", action="store_true", help="reject programs that are still running after --run-timeout")
    p.add_argument("-o", "--out", type=Path, help="save the source here")
    p.add_argument("--prg", type=Path, help="save the built .prg here")
    p.add_argument("--base-url", default="http://127.0.0.1:8000/v1")
    p.add_argument("--model", default="commodore3.8-27b")
    p.add_argument("--api-key", default="local")
    p.add_argument("--max-repairs", type=int, default=3)
    p.add_argument("--temperature", type=float, default=0.2)
    p.add_argument("--max-tokens", type=int, default=4096)
    p.add_argument("--run-timeout", type=float, default=20)
    p.add_argument("--request-timeout", type=float, default=900)
    args = p.parse_args(argv)
    args.no_think = True  # trained and evaluated with thinking off

    language = args.lang or guess_language(args.prompt)
    log = lambda msg: print(msg, file=sys.stderr)  # noqa: E731 - stdout carries only the program
    log(f"language: {language}")
    try:
        code, res = write_program(args.prompt, language, args, log)
    except (urllib.error.URLError, TimeoutError) as exc:
        log(f"model server not reachable at {args.base_url}: {exc}")
        return 2
    if code is None:
        log("no program produced")
        return 1

    print(code, end="")
    status = res.status if res else "failed"
    if res and res.status == "verified":
        run = next((s for s in res.stages if s.name == "run"), None)
        if run and run.detail.get("run_status") == "timeout":
            log(f"note: still running after {args.run_timeout:.0f}s (accepted; use --must-finish to require an end)")
    if args.out:
        args.out.write_text(code, encoding="utf-8")
        log(f"saved {args.out}")
    if args.prg:
        log(f"saved {args.prg}" if save_prg(code, language, args.prg) else "could not build the .prg")
    log(status.upper() if status == "verified" else f"{status.upper()}: last attempt still fails, check it yourself")
    return 0 if status == "verified" else 1


if __name__ == "__main__":
    sys.exit(main())
