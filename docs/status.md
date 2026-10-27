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

## 27-10-2026: dataset v0.1 and proof run (phases 2–3)

### Dataset v0.1 (`c38-synth`, not in git: `data/v0.1`)
- 200 tasks from 29 parametrized families (`commodore38/data/families.py`), deliberately different from the benchmark families. Every task has a computed expected result (screen text or memory/registers).
- Teacher: Qwen3.8-27B (MTPLX) with skill document + checker loop (≤3 repairs). Only answers that pass the full pipeline are kept. The sample itself contains only the short "bare" system prompt + task + clean code block.
- Result: **165 verified samples** (C64 BASIC 66, C128 BASIC 65, KickAss 34) → 149 train / 16 valid. 35 rejected, mostly real model errors (Collatz with two `if`s in a row, a wrong LCM algorithm, `bpl` as an unsigned comparison, wrong screen codes).
- Pipeline bug found and fixed: a program that poked text **below** the cursor ended with `ready.` not on the last line, and was marked as a timeout. 3 samples were recovered with `c38-synth --reverify-rejected`.

### Proof run (`train/configs/proefrun.yaml`)
- QLoRA via mlx-lm 0.32.2 directly on the 4/8-bit MLX pack of Qwen3.8-27B (no bf16 download needed for this). LoRA rank 16 on all 64 blocks, 116.7M trainable parameters (0.43%), 80 iterations × batch 4, max seq 2048, loss only on the answer.
- `commodore38/train/lora.py`: mlx-lm renders training samples with thinking **on** by default. For Qwen3.8 that injects a hidden "Reasoning effort is set to xhigh" system text and puts the mask before the `<think></think>` block. The launcher sets `enable_thinking=False`, so training matches inference exactly (checked token for token).
- Validation loss 0.80 → 0.21 (it. 40) → 0.167 (it. 60) → **0.142** (it. 80); still falling, no overfitting.
- **Speed: ±10 tokens/s** (≈50 s per iteration, 34.3k tokens in ±70 min). Extrapolated, a full run of 5–20M tokens would take 6–23 days. This is the bottleneck from §6.0; see the speed tests below.

### Eval: base vs. adapter (same mlx-lm server, same 4-bit weights, no skill document, thinking off, 1 attempt)
| | Qwen3.8 base | + adapter proefrun-v0.1 |
|---|---|---|
| C64 BASIC (14) | 7% (lenient 64%) | **79%** |
| C128 BASIC (10) | 0% (lenient 60%) | **60%** |
| KickAss (6) | 0% | **33%** |
| checker clean | 33% | 97% |

- After 149 examples the conventions (lowercase, `chr$()`, Kick Assembler syntax) have been learned. Without the skill, C128 scores higher than the base model *with* skill on its first attempt (40%).
- New error pattern: C128 statements (`graphic`, `scnclr`) in C64 code, i.e. dialect confusion from the mixed data. The checker catches it, but it is a reason for clearer platform signals in the system prompt and more C64 data.
- Remaining errors are logic and knowledge: wrong color numbers, screen codes, sprite setup, IRQ setup. That fits §3 principle 2: facts belong in RAG/skill, not only in fine-tuning.
- Indicative: 30 tasks, one run. The adapter (`adapters/proefrun-v0.1`, 467 MB) is local and not in git.

### Speed tests (6 iterations each, M3 Max 128 GB)
| Variant | tok/s | Note |
|---|---|---|
| all 64 layers, grad checkpoint, batch 4 (proof run) | 10 | reference |
| all 64 layers, **without** grad checkpoint, batch 4 | out of memory | Metal OOM |
| all 64 layers, without grad checkpoint, batch 1 | 6, then OOM | |
| **last 16 layers**, grad checkpoint, batch 4 | **21–22** | val loss after 6 it. 0.29 (all layers: 0.36) |

- Gradient checkpointing is required: the GatedDeltaNet activations do not fit without it, not even at batch 1.
- LoRA on the last 16 blocks only makes the backward pass much shorter → 2× faster, with no visible loss of learning ability in this short test. Still to be confirmed with a full run plus eval.
- Extrapolation at 22 tok/s: 5–20M training tokens ≈ 2.5–10.5 days. Note: tok/s counts all tokens including the prompt, so short system prompts help directly.
- Further options: keep the dataset compact (quality > quantity, §6.0), shorter system prompt in the samples, and possibly raise the macOS GPU memory limit (`iogpu.wired_limit_mb`, needs sudo; not changed). If it stays too slow, the cloud question goes back to the client (§6.0); that is not my call.

### Next
1. Merge the `checker-fixes` branches in the skillset repos, then pin the commits on `main`.
2. Re-run the baseline with the improved checkers, with several runs per variant (variance) and thinking on/off.
3. Extend the benchmark toward 50–100 tasks per platform, keeping a fixed held-out test set.
4. Phase 2: dataset pipeline (collect → license check → normalize → verify) on the own repos from §1.1.
5. Proof run with mlx-lm (phase 3): does `qwen3_5` load for training, and measure tokens/s.
