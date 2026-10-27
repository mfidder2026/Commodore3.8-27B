# Status

## 27-10-2026: start of phases 1 and 2

### Built
- **Verification pipeline** (`commodore38/verify.py`, CLI `c38-verify`): syntax checker → bas2prg / petcat / KickAss → VICE headless → expectations (screen text of the program output + memory and registers via the binary monitor). Exit codes 0 verified / 1 failed / 2 incomplete.
  - Working: C64 BASIC, C128 BASIC (checker + bas2prg + VICE), Plus/4 and PET BASIC (petcat + VICE; no checker yet → always `incomplete`).
  - KickAss: complete (checker + Kick Assembler 5.25 on openjdk 27 + VICE). KickAss.jar lives locally in `kick/` (not in git, redistribution not cleared).
- **Unified checker interface** (`commodore38/checkers.py`): all three skillset checkers as subprocesses, normalized to JSON. The C64 BASIC checker has no `--json`, so its text output is parsed.
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

### Findings for the skillset repos
- `c64_syntax_checker.py`: does not flag `else` (forbidden in BASIC V2 per the skill), has no `--json`, and does not warn about uppercase source (breaks `-i`).
- `c128_syntax_checker.py`: does not flag `mod` as a non-existent operator.

### Next
1. Fix the checker gaps above in the skillset repos (and pin new commits in `scripts/fetch_external.sh`).
2. Extend the benchmark toward 50–100 tasks per platform, keeping a fixed held-out test set.
3. Baseline with thinking on, and several runs per variant (variance).
4. Phase 2: dataset pipeline (collect → license check → normalize → verify) on the own repos from §1.1.
5. Proof run with mlx-lm (phase 3): does `qwen3_5` load for training, and measure tokens/s.
