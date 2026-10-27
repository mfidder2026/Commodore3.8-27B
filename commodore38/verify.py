"""Verification pipeline (brief §5.4): checker -> build -> VICE run -> expectations.

A sample counts as verified only when every stage that applies passes. Stages
whose tools are not installed are reported as ``skipped`` and make the overall
result ``incomplete`` rather than passed, so unverified code never slips into
the dataset.

CLI::

    c38-verify program.bas --lang c64-basic --expect-text "hello"
    c38-verify demo.asm --lang c64-kickass --allow-timeout --json

Exit codes: 0 = verified, 1 = failed, 2 = incomplete (a tool was missing).
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from .build import build
from .checkers import CHECKERS, check_file
from .config import Toolchain, load_toolchain
from .platforms import get_platform
from .vice import run_prg

# language -> platform key
LANGUAGES = {
    "c64-basic": "c64",
    "c64-kickass": "c64",
    "c128-basic": "c128",
    "plus4-basic": "plus4",
    "pet-basic": "pet",
}


@dataclass
class MemoryCheck:
    addr: int
    value: int
    mask: int = 0xFF   # e.g. 0x0F for VIC color registers, whose upper bits read as 1

    @classmethod
    def from_dict(cls, data: dict) -> "MemoryCheck":
        def num(v):
            return int(v[1:], 16) if isinstance(v, str) and v.startswith("$") else int(v, 0) if isinstance(v, str) else v
        return cls(num(data["addr"]), num(data["value"]), num(data.get("mask", 0xFF)))


@dataclass
class Expectation:
    """What a successful run must show.

    Text matching is case-insensitive and only looks at the program's own
    output (below the autostart 'run' line), not at the boot banner.
    """
    screen_contains: list[str] = field(default_factory=list)
    allow_timeout: bool = False   # programs that never return to READY (games, raster loops)
    memory: list[MemoryCheck] = field(default_factory=list)
    screen_excludes: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict | None) -> "Expectation":
        data = data or {}
        return cls(
            list(data.get("screen_contains", [])),
            bool(data.get("allow_timeout", False)),
            [MemoryCheck.from_dict(m) for m in data.get("memory", [])],
            list(data.get("screen_excludes", [])),
        )


@dataclass
class Stage:
    name: str
    status: str   # "passed" | "failed" | "skipped"
    detail: dict = field(default_factory=dict)


@dataclass
class VerifyResult:
    language: str
    stages: list[Stage] = field(default_factory=list)

    @property
    def status(self) -> str:
        if any(s.status == "failed" for s in self.stages):
            return "failed"
        if any(s.status == "skipped" for s in self.stages):
            return "incomplete"
        return "verified"

    @property
    def exit_code(self) -> int:
        return {"verified": 0, "failed": 1, "incomplete": 2}[self.status]

    def to_dict(self) -> dict:
        return {
            "language": self.language,
            "status": self.status,
            "stages": [{"name": s.name, "status": s.status, **s.detail} for s in self.stages],
        }

    def feedback(self) -> str:
        """Short human/model-readable summary of the first failing stage."""
        for s in self.stages:
            if s.status == "failed":
                return f"{s.name} failed: {json.dumps(s.detail, ensure_ascii=False)}"
        return self.status


def verify_file(
    path: Path,
    language: str,
    expect: Expectation | None = None,
    run: bool = True,
    timeout: float = 20.0,
    toolchain: Toolchain | None = None,
) -> VerifyResult:
    toolchain = toolchain or load_toolchain()
    expect = expect or Expectation()
    if language not in LANGUAGES:
        raise ValueError(f"unknown language {language!r}; known: {', '.join(LANGUAGES)}")
    result = VerifyResult(language)

    # 1. syntax checker
    if language in CHECKERS:
        chk = check_file(path, language, toolchain)
        status = {0: "passed", 1: "failed"}.get(chk.exit_code, "skipped")
        detail = chk.to_dict() if status != "skipped" else {"reason": chk.raw_output.strip()[:500]}
        result.stages.append(Stage("check", status, detail))
        if status == "failed":
            return result
    else:
        result.stages.append(Stage("check", "skipped", {"reason": f"no syntax checker for {language} yet"}))

    # 2. tokenize / assemble
    with tempfile.TemporaryDirectory(prefix="c38-build-") as tmp:
        built = build(path, language, Path(tmp), toolchain)
        if not built.ok:
            not_configured = "not found" in built.log or "not configured" in built.log
            result.stages.append(Stage("build", "skipped" if not_configured else "failed",
                                       {"tool": built.tool, "log": built.log.strip()[-1000:]}))
            return result
        result.stages.append(Stage("build", "passed", {"tool": built.tool, "bytes": built.prg.stat().st_size}))

        # 3. run in the emulator
        if not run:
            return result
        ran = run_prg(built.prg, get_platform(LANGUAGES[language]), timeout=timeout,
                      peeks=[m.addr for m in expect.memory], toolchain=toolchain)

    detail = {"run_status": ran.status, "seconds": round(ran.seconds, 2), "screen": ran.screen}
    if ran.detail:
        detail["detail"] = ran.detail
    if ran.status == "error":
        result.stages.append(Stage("run", "skipped", detail))
        return result
    run_ok = ran.status == "finished" or (ran.status == "timeout" and expect.allow_timeout)
    result.stages.append(Stage("run", "passed" if run_ok else "failed", detail))
    if not run_ok:
        return result

    # 4. expected screen output and memory state
    if expect.screen_contains or expect.screen_excludes or expect.memory:
        output = "\n".join(ran.output_lines()).lower()
        missing = [t for t in expect.screen_contains if t.lower() not in output]
        missing += [f"(must not appear) {t}" for t in expect.screen_excludes if t.lower() in output]
        wrong = []
        for m in expect.memory:
            actual = ran.memory.get(m.addr)
            if actual is None or actual & m.mask != m.value:
                wrong.append({"addr": f"${m.addr:04X}", "expected": m.value,
                              "actual": None if actual is None else actual & m.mask})
        failed = bool(missing or wrong)
        result.stages.append(Stage("expect", "failed" if failed else "passed", {"missing": missing, "memory": wrong}))
    return result


def verify_source(source: str, language: str, **kwargs) -> VerifyResult:
    suffix = ".asm" if language.endswith("kickass") else ".bas"
    with tempfile.TemporaryDirectory(prefix="c38-src-") as tmp:
        path = Path(tmp) / f"program{suffix}"
        path.write_text(source, encoding="utf-8")
        return verify_file(path, language, **kwargs)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify Commodore source: check, build, run in VICE.")
    parser.add_argument("file", type=Path)
    parser.add_argument("--lang", required=True, choices=sorted(LANGUAGES))
    parser.add_argument("--expect-text", action="append", default=[], help="text the program must print")
    parser.add_argument("--allow-timeout", action="store_true", help="accept programs that keep running")
    parser.add_argument("--no-run", action="store_true", help="stop after the build stage")
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    res = verify_file(args.file, args.lang, Expectation(args.expect_text, args.allow_timeout),
                      run=not args.no_run, timeout=args.timeout)
    if args.json:
        print(json.dumps(res.to_dict(), indent=2, ensure_ascii=False))
    else:
        for s in res.stages:
            print(f"{s.name:<7} {s.status}")
        if res.status != "verified":
            print(res.feedback())
        print(res.status.upper())
    return res.exit_code


if __name__ == "__main__":
    sys.exit(main())
