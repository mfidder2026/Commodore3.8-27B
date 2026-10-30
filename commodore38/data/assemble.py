"""Combine synth output directories into one dataset, with an optional cleanup pass.

  python -m commodore38.data.assemble --from data/v0.2 data/v0.3-extra --out data/v0.3 \
      --strip-c128-boilerplate

--strip-c128-boilerplate: two thirds of the v0.2 C128 samples open with the
teacher's habit "graphic 0 / scnclr 0 / color 0,1:color 4,1:color 5,2", and the
v0.2 model started writing those C128 statements into C64 programs. When the
task does not ask for clearing the screen or for colors, those lines are dropped
and the program is verified again; the stripped version is kept only if it
still passes, otherwise the original stays.

--strip-trailing-clear: programs whose last statement (before end) is a lone
`print chr$(147)` after they set something up. In v0.4 the teacher ended 47 of 49
border/background programs that way; the v0.3 model learned the habit and wiped
characters it had just poked. Same rule: dropped, re-verified, kept only if it passes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

from ..verify import Expectation, verify_source
from .families import Task
from .synth import make_sample, normalize, write_splits

BOILERPLATE = re.compile(r"^\d+\s+((graphic 0|scnclr( 0)?|color \d+,\d+)\s*(:\s*|$))+$")
# Tasks that legitimately need the clear or color statements
NEEDS_SCREEN_SETUP = re.compile(r"clear|cls|empty screen|colou?r|border|background|wis|kleur|rand|achtergrond", re.I)


TRAILING_CLEAR = re.compile(r"^\d+\s+print\s*chr\$\(147\);?$")
SKIP_LINE = re.compile(r"^\d+\s+(rem\b.*|end)$")


def code_of(row: dict) -> str:
    return row["messages"][-1]["content"].split("\n", 1)[1].rsplit("```", 1)[0]


def strip_boilerplate(code: str) -> str:
    return "".join(l + "\n" for l in code.splitlines() if not BOILERPLATE.match(l.strip()))


def strip_trailing_clear(code: str) -> str:
    lines = code.splitlines()
    body = [i for i, l in enumerate(lines) if l.strip() and not SKIP_LINE.match(l.strip())]
    if len(body) < 2 or not TRAILING_CLEAR.match(lines[body[-1]].strip()):
        return code
    return "".join(l + "\n" for i, l in enumerate(lines) if i != body[-1])


def try_strip(row: dict, run_timeout: float) -> dict | None:
    meta = row["meta"]
    prompt = row["messages"][1]["content"]
    if meta["language"] != "c128-basic" or NEEDS_SCREEN_SETUP.search(prompt):
        return None
    return reverify(row, strip_boilerplate(code_of(row)), run_timeout, "c128 boilerplate stripped, re-verified")


def try_strip_trailing_clear(row: dict, run_timeout: float) -> dict | None:
    if row["meta"]["language"] == "c64-kickass":
        return None
    return reverify(row, strip_trailing_clear(code_of(row)), run_timeout, "trailing clear-screen dropped, re-verified")


def reverify(row: dict, stripped: str, run_timeout: float, note: str) -> dict | None:
    meta = row["meta"]
    prompt = row["messages"][1]["content"]
    if stripped == code_of(row) or not stripped.strip():
        return None
    res = verify_source(stripped, meta["language"], expect=Expectation.from_dict(meta["expect"]), timeout=run_timeout)
    if res.status != "verified":
        return None
    sample = make_sample(Task(meta["family"], meta["language"], prompt, meta["expect"]), stripped)
    sample_id = hashlib.sha256(json.dumps(sample).encode()).hexdigest()[:12]
    return {"id": sample_id, **sample, "meta": {**meta, "note": note}}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--from", dest="sources", type=Path, nargs="+", required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--strip-c128-boilerplate", action="store_true")
    p.add_argument("--strip-trailing-clear", action="store_true")
    p.add_argument("--seed", type=int, default=38)
    p.add_argument("--valid-fraction", type=float, default=0.1)
    p.add_argument("--run-timeout", type=float, default=20)
    args = p.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=False)
    seen, stripped, cleared = set(), 0, 0
    with (args.out / "all.jsonl").open("w", encoding="utf-8") as all_f, \
         (args.out / "rejected.jsonl").open("w", encoding="utf-8") as rej_f:
        for src in args.sources:
            for line in (src / "all.jsonl").open(encoding="utf-8"):
                row = json.loads(line)
                if args.strip_c128_boilerplate and (new := try_strip(row, args.run_timeout)):
                    row, stripped = new, stripped + 1
                if args.strip_trailing_clear and (new := try_strip_trailing_clear(row, args.run_timeout)):
                    row, cleared = new, cleared + 1
                key = normalize(code_of(row))
                if key in seen:
                    continue
                seen.add(key)
                all_f.write(json.dumps(row, ensure_ascii=False) + "\n")
            rej_f.write((src / "rejected.jsonl").read_text(encoding="utf-8"))
    print(f"{stripped} C128 samples stripped of boilerplate, {cleared} trailing clear-screens dropped")
    write_splits(args.out, args.seed, args.valid_fraction)
    return 0


if __name__ == "__main__":
    sys.exit(main())
