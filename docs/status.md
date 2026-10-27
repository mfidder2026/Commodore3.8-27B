# Status

## 27-10-2026: start of phases 1 and 2

### Built
- **Verification pipeline** (`commodore38/verify.py`, CLI `c38-verify`): syntax checker → bas2prg / petcat / KickAss → VICE headless → expectations (screen text of the program output + memory and registers via the binary monitor). Exit codes 0 verified / 1 failed / 2 incomplete.
  - Working: C64 BASIC, C128 BASIC (checker + bas2prg + VICE), Plus/4 and PET BASIC (petcat + VICE; no checker yet → always `incomplete`).
  - KickAss: complete (checker + Kick Assembler 5.25 on openjdk 27 + VICE). KickAss.jar lives locally in `kick/` (not in git, redistribution not cleared).
- **Unified checker interface** (`commodore38/checkers.py`): all three skillset checkers as subprocesses with `--json`, normalized to one structure.
- **Commodore-Eval v0** (`commodore38/eval/`, CLI `c38-eval`): 30 tasks (14 C64 BASIC, 10 C128 BASIC, 6 KickAss), each with a reference solution. `c38-eval --references`: all 30 references verify.
- Tests: `pytest` (17, of which 10 run end to end through VICE/KickAss).

### Baseline (phase 1), stock Qwen3.8-27B
Model: `Youssofal/Qwen3.8-27B-MTPLX-Optimized-Speed` via MTPLX 2.12.2 (quantized MTPLX pack, not bf16), thinking off, temperature 0.2. One run per variant, so these are indicative numbers and not statistically solid yet.

| Variant | C64 BASIC (14) | C128 BASIC (10) | KickAss (6) |
|---|---|---|---|
| bare, pass@1 strict | 7% | 0% | 0% (checker: 0% clean) |
| bare, pass@1 lenient (uppercase listing → lowercase) | 64% | 60% | 0% |
| skills + checker loop, pass@1 | 86% | 40% | 83% |
| skills + checker loop, after ≤3 repairs | 86% | 60% | 100% |

Observations:
- Without the skill document, the model writes classic UPPERCASE listings, which break the lowercase + `bas2prg -i` convention (D2). This is the biggest single source of errors. The lenient column separates it from logic errors.
- Without the skill, KickAss code uses `.org`, `add` and similar (other assemblers or hallucinations). With the skill, the checker is 100% clean.
- C128 is clearly weaker than C64, even with the skill: `MOD` (does not exist in BASIC 7.0), VIC vs BASIC color numbering in `COLOR`, wrong screen and color addresses, uppercase string contents.
- Measurement error found and fixed: with a `.file` directive, KickAss writes its own file name and ignores `-o`. The pipeline now reads the file name from the KickAss log. The 4 wrongly rejected raster IRQ attempts were verified again and are correct; the KickAss figures above are after that fix.
- Answers are short (~1–2 s each with MTPLX), so the eval itself is cheap.

### Checker fixes in the skillset repos (branch `checker-fixes`, pinned in `scripts/fetch_external.sh`)
- `c64_syntax_checker.py` (+ NL): §3.2 keywords from other dialects (`else`, `while`, `mod`, `cls`, `instr(`, …) as errors without false positives on variables such as `do=5` or `key(3)`. Uppercase in code = error, in strings = warning. `--json`. `then <n>` targets are now checked (previously false "unreachable" warnings and no error on a missing target). No crash on a jump to a non-existent line.
- `c128_syntax_checker.py`: `MOD` between operands → `NOT_IN_BASIC7`, plus a regression test.
- Replayed against all earlier model answers: every failing C64 answer is now caught statically (uppercase listings, and `mod` in the four failed fizzbuzz attempts); the four failed C128 `else` attempts are caught on `MOD`. No verified answer and no reference gets a false error.
- The baseline figures above are from before these fixes. In the skills-loop the model now gets concrete checker feedback for these errors, so a re-run will probably come out higher.

### Next
1. Merge the `checker-fixes` branches in the skillset repos, then pin the commits on `main`.
2. Re-run the baseline with the improved checkers, with several runs per variant (variance) and thinking on/off.
3. Extend the benchmark toward 50–100 tasks per platform, keeping a fixed held-out test set.
4. Phase 2: dataset pipeline (collect → license check → normalize → verify) on the own repos from §1.1.
5. Proof run with mlx-lm (phase 3): does `qwen3_5` load for training, and measure tokens/s.
