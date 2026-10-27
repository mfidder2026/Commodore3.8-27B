"""Turn source into a runnable .prg: BASIC tokenizers and assemblers."""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from .config import Toolchain, load_toolchain


@dataclass
class BuildResult:
    tool: str
    ok: bool
    prg: Path | None
    log: str


# language -> (repo, script) for the skillset tokenizers
BAS2PRG = {
    "c64-basic": ("c64_basic_ai_skillset", "bas2prg.py"),
    "c128-basic": ("c128_basic_ai_skillset", "bas2prg.py"),
}

# language -> (petcat BASIC version, load address in hex), for dialects without a
# skillset tokenizer yet. The load address is explicit: petcat's default is wrong for some.
PETCAT_VERSIONS = {
    "plus4-basic": ("3", "1001"),
    "pet-basic": ("40", "0401"),
}


def _run(cmd: list[str], tool: str, out: Path, timeout: int = 120) -> BuildResult:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return BuildResult(tool, False, None, f"{tool} timed out")
    log = proc.stdout + proc.stderr
    ok = proc.returncode == 0 and out.is_file() and out.stat().st_size > 2
    return BuildResult(tool, ok, out if ok else None, log)


def build(source_path: Path, language: str, out_dir: Path, toolchain: Toolchain | None = None) -> BuildResult:
    toolchain = toolchain or load_toolchain()
    out = out_dir / (source_path.stem + ".prg")
    out.unlink(missing_ok=True)

    if language in BAS2PRG:
        repo, script = BAS2PRG[language]
        script_path = toolchain.external_dir / repo / script
        if not script_path.is_file():
            return BuildResult("bas2prg", False, None, f"bas2prg not found: {script_path}")
        return _run([sys.executable, str(script_path), str(source_path), "-o", str(out), "-i"], "bas2prg", out)

    if language in PETCAT_VERSIONS:
        petcat = toolchain.vice("petcat")
        if not petcat:
            return BuildResult("petcat", False, None, "petcat not found (VICE not configured)")
        version, load = PETCAT_VERSIONS[language]
        return _run([petcat, f"-w{version}", "-l", load, "-o", str(out), "--", str(source_path)], "petcat", out)

    if language == "c64-kickass":
        if not (toolchain.java and toolchain.kickass_jar):
            return BuildResult("kickass", False, None, "KickAss not configured: set java and kickass_jar in toolchain.local.toml")
        res = _run([toolchain.java, "-jar", toolchain.kickass_jar, str(source_path), "-o", str(out)], "kickass", out)
        if not res.ok:
            # A .file directive makes KickAss write its own file name next to the source and ignore -o.
            written = _kickass_written_prg(res.log)
            if written and written.is_file() and written.stat().st_size > 2:
                return BuildResult("kickass", True, written, res.log)
        return res

    return BuildResult("none", False, None, f"no build tool for language {language!r}")


def _kickass_written_prg(log: str) -> Path | None:
    out_dir = re.search(r"^Output dir: (.+)$", log, re.MULTILINE)
    prgs = re.findall(r"^Writing prg file: (.+)$", log, re.MULTILINE)
    if not (out_dir and prgs):
        return None
    return Path(out_dir.group(1).strip()) / prgs[0].strip()
