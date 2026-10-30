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

## 28-10-2026: experiment with a smaller model (Qwen3.5-9B)

There is no official Qwen3.8 below 27B (Qwen3.8 = 27B, Flash-Next MoE 99 GB in 4-bit, 2.4T). The smallest official option with the same architecture is **Qwen3.5-9B** (Apache-2.0, `qwen3_5`, 32 layers), converted to MLX 4-bit (5.2 GB; bf16 stays in the HF cache). Identical dataset v0.1 and hyperparameters (`train/configs/proefrun-9b.yaml`), eval via `scripts/eval_mlx.sh`.

| | Qwen3.8-27B | Qwen3.5-9B |
|---|---|---|
| Training proof run (80 it.) | ±70 min, ~10 tok/s | **±19 min, ~31–35 tok/s (3.5× faster)** |
| Val loss start → end | 0.80 → 0.142 | 0.96 → 0.181 |
| Base pass@1 (lenient) | 3% (50%) | 3% (27%) |
| **+ adapter pass@1** | **63%** | **53%** |
| – C64 BASIC (14) | 79% | 64% |
| – C128 BASIC (10) | 60% | 60% |
| – KickAss (6) | 33% | 17% |
| checker clean with adapter | 97% | 90% |

- The 9B trains 3.5× faster, and the fine-tune brings it a long way (3% → 53%), but it stays behind the 27B, most clearly on C64 BASIC and assembler. Its base knowledge is clearly weaker (lenient 27% vs 50%).
- Indicative: one run on 30 tasks. 63% vs 53% is 3 tasks; on KickAss one task = 17%.
- Projection for a full run (5–20M tokens): 9B all layers ≈ 1.7–7 days; 27B with 16 layers ≈ 2.5–10.5 days.

## 28-10-2026: benchmark v1 and dataset v0.2

### Benchmark: 120 tasks
- `commodore38/eval/families.py`: parametrized versions of the 30 hand-written tasks (eval only, disjoint from the training families), 3 instances each with seed 1038 → `eval/tasks/generated-v1.json` (90). Together with the 30 originals: **120 tasks**; all references verify.

### Dataset v0.2 (`data/v0.2`, not in git)
- 1000 tasks from 63 training families (28 BASIC, 9 C64-specific, 9 C128, 17 KickAss), decontaminated against the benchmark. Same teacher setup as v0.1 (Qwen3.8-27B MTPLX + skill + checker loop).
- **877 verified samples** (C64 BASIC 352, C128 BASIC 324, KickAss 201) → 790 train / 87 valid. 123 rejected. Generation ±2.5 hours.
- Weak families (yield): `dec` 0/10, `lcm` 4/23, `collatz` 9/21, `countdown_table` 8/15, `popcount` 9/16, `to_binary` 14/24. Spot checks show real model errors, not expectation errors:
  - `dec`: the teacher uses `val("7a7e")` instead of C128 `dec()`. A hand-written `print dec("7a7e")` verifies, so the pipeline is fine.
  - `to_binary`: `str$(b)` adds a leading space; `chr$(48+n and 1)` has the wrong operator precedence.
- Consequence: things the teacher doesn't know itself do not end up in the data (`dec` is missing completely). For such gaps, hand-written or skill-derived examples are needed, or a stronger teacher.

### Training v0.2 (`train/configs/v0.2.yaml`)
- Base: own MLX 4-bit conversion of the official Qwen/Qwen3.8-27B; LoRA rank 16 on the last 16 of 64 blocks (29.2M trainable parameters); 2 epochs = 400 optimizer updates at effective batch 4.
- The first attempt with batch 4 crashed at iteration 115 on a Metal OOM: one sample is 1017 tokens (median 207), so a batch of 4 gets padded to that length. Restarted from scratch with batch 2 × gradient accumulation 2: same effective batch, half the peak memory, 23–27 tok/s.
- Validation loss 0.896 → 0.180 (50 updates) → 0.121 (1 epoch) → **0.109** (2 epochs); levels off in epoch 2 without rising. ±2.5 hours.

### Eval on the 120-task benchmark (bare, thinking off, temperature 0.2, 1 attempt)
| | Base (own 4-bit) | v0.1 adapter (MTPLX pack, 64 layers, 149 samples) | v0.2 adapter (own 4-bit, 16 layers, 790 samples) | v0.2 merged → MLX 4-bit |
|---|---|---|---|---|
| C64 BASIC (56) | 7% (lenient 55%) | 71% | 70% | 75% |
| C128 BASIC (40) | 0% (lenient 57%) | 65% | **82%** | 80% |
| KickAss (24) | 0% | 50% | 46% | 62% |
| **Total (120)** | **3%** (lenient 45%) | **65%** | **69%** | **74%** |
| checker clean | 31% | 93% | 93% | 93% |

- v0.2 is clearly better on C128 (+17 points). On C64 and KickAss it's no better than v0.1, despite 5× more data. Not a clean comparison: v0.1 has LoRA on all 64 layers and a different base quantization.
- Merged vs adapter: 16 of 120 tasks differ, in both directions. That is the noise level of one run at temperature 0.2. Differences of ±5 points are not significant; for real comparisons, several runs or temperature 0 are needed.
- Error analysis v0.2 C64 BASIC:
  - **`sqrt(`** instead of `sqr(` (4× in `primes`). The checker didn't catch it: fixed in `c64_basic_ai_skillset` (849b187); `sqrt(` is now an error. No false positives on the 352 C64 samples or the references.
  - **C128 boilerplate in C64 code** (`graphic 0 / scnclr 0 / color …` for "clears the screen", 3×). Every C128 sample in v0.2 starts with that block, and there is no C64 training family for clearing the screen.
  - Color numbers (`colors`), sprite setup (`sprite`) and long answers that hit the max-token limit (4096) without a code block.
- Points for v0.3: C64 families with `chr$(147)`/clear screen and colors; fewer identical C128 boilerplate headers; samples for knowledge the teacher lacks itself (`dec`); retry `sqrt` failures now that the checker gives feedback.

### Phase 4: merged model
- `commodore38/train/merge_hf.py`: applies the LoRA deltas to the **original** HF bf16 shards (`W += scale·(A·B)ᵀ`). Vision tower, MTP head, config and tokenizer stay byte-for-byte the original. `mlx_lm fuse` drops those and renames weights, which is unsuitable for publication and for llama.cpp. Layout checked against `mlx_lm fuse`: equal up to bf16 rounding.
- Result: `models/commodore3.8-27b-v0.2` (HF format, bf16, 52 GB) and `models/commodore3.8-27b-v0.2-mlx-4bit` (16 GB, loadable in LM Studio as an MLX model). Not in git.
- The merged model scores the same as adapter + base (see table), so the merge is correct.
- **GGUF** (with permission from the client): llama.cpp 0.7.0 via brew; `convert_hf_to_gguf.py` from the llama.cpp source (`external/llama.cpp`, commit 8642541) in its own venv `.venv-gguf` (Python 3.12).
  - `models/gguf/Commodore3.8-27B-v0.2-BF16.gguf` (51 GB) → `llama-quantize` → **`Commodore3.8-27B-v0.2-Q4_K_M.gguf` (16 GB, 4.92 bpw)**. Text model only, no vision projector (mmproj).
  - Validated through `llama-server --jinja` with the 120 tasks: **72%** (C64 79%, C128 80%, KickAss 42%, checker clean 94%). Same within noise as MLX 4-bit (74%); KickAss differs by 5 of 24 tasks. ±19 tok/s generation on the M3 Max.
- Client decision 29-10-2026: **no 9B variant** (quality too low); M1 stays 27B only. Releases: GGUF and MLX.
- **MTPLX pack** (`scripts/build_mtplx.sh`, recipe `train/mtplx/recipe-optimized-speed.json`): 4-bit body (group 32), 8-bit embeddings/lm_head/last MLP blocks, MTP head kept bf16. `~/.mtplx/models/Commodore3.8-27B-v0.2-MTPLX-Q4` (20 GB).
  - MTPLX 2.12.2 `forge build` converts fine, but its MTP contract calibration fails for Qwen3.8-27B from bf16, also on the untouched official weights (control run: `contract_candidates_tested: 0`). Workaround: write the contract of the working Youssofal Optimized-Speed pack (same architecture and head) into `config.json`, then `mtplx forge verify --stamp` measures it and stamps the pack only when the rows pass. Result: tier *verified*, depth 3 = 43 tok/s vs 17.6 tok/s autoregressive in forge verify.
  - 120 tasks via `mtplx serve --mtp`: **72%** (C64 75%, C128 82%, KickAss 46%, checker clean 94%), **32.8 tok/s** generation in the eval (≈1.75× MLX 4-bit).
- Model card `docs/model-card.md`, with `LICENSE` and `NOTICE`, is copied into the MLX folder, the GGUF folder and the MTPLX pack. Not published: upload to Hugging Face waits for approval.

## 29-10-2026: dataset v0.3, training blocked

### Dataset v0.3 (`data/v0.3`, not in git)
- New C64 families from the error analysis: `c64_clear_print`, `c64_border_background`, `c64_color_print`, `c64_square_root`; `c128_dec` names DEC explicitly. Generated with `c38-synth --families …` (teacher: MTPLX Optimized-Speed pack) into `data/v0.3-extra`: 176 kept of 300.
  - Yield per family (kept/failed): border_background 30/0, color_print 28/1, square_root 31/0, dec 14/1, to_binary 19/28, countdown_table 12/7, popcount 13/8, lcm 13/31, collatz 9/31, clear_print 7/17.
- `python -m commodore38.data.assemble --from data/v0.2 data/v0.3-extra --out data/v0.3 --strip-c128-boilerplate`: 223 C128 samples lost the `graphic 0 / scnclr / color` header (each re-verified in VICE; kept only if it still passes). Total **1052 samples (947 train / 105 valid)**, longest 1055 tokens (the same outlier as v0.2).
- `train/configs/v0.3.yaml`: v0.2 recipe, 950 micro-batches = 475 updates ≈ 2 epochs.

### Training blocked by the GPU driver
- Two v0.3 runs stalled at the first step. A smoke test with the **v0.2 config that trained fine on 28-10** is just as slow: 4 steps in ~20 min instead of ~3 s per step. Stack samples: the time goes into `MetalAllocator::malloc` → `ResidencySets::insert` → `IOGPUMetalResidencySet commit` in the Apple GPU driver.
- Same MLX (0.32.4) and mlx-lm (0.32.2) as on 27-10, same macOS 27.0.1, 81% of memory free. Inference is unaffected (MLX generate and MTPLX serve run at normal speed). Diagnosis: degraded driver state after 3 days of uptime with heavy Metal use. Fix: **reboot the Mac**, then:
  ```
  caffeinate -i .venv-train/bin/python -m mlx_lm lora --config train/configs/v0.3.yaml > runs/train-v0.3.log 2>&1
  scripts/eval_mlx.sh …   # 120 tasks, several runs; compare with v0.2
  ```
  If v0.3 wins: `merge_hf` → `mlx_lm convert -q --q-bits 4 --q-group-size 32` → GGUF Q4_K_M → `scripts/build_mtplx.sh models/commodore3.8-27b-v0.3 Commodore3.8-27B-v0.3-MTPLX-Q4`.
- Until then, **v0.2 is the release**, and its MTPLX Q4 pack is running: `mtplx serve --model ~/.mtplx/models/Commodore3.8-27B-v0.2-MTPLX-Q4 --port 8000 --model-id commodore3.8-27b --mtp`.

## 30-10-2026: v0.3 trained and evaluated, v0.2 stays the release

### Training
- After the reboot the driver stall is gone: v0.3 trained normally (950 iterations, ~3 h, same tok/s as v0.2). Final val loss 0.115 on the v0.3 validation set (not comparable with v0.2's 0.109: different set).
- Built from it: `models/commodore3.8-27b-v0.3` (merged bf16), `models/commodore3.8-27b-v0.3-mlx-4bit`, `models/gguf/Commodore3.8-27B-v0.3-Q4_K_M.gguf`, `~/.mtplx/models/Commodore3.8-27B-v0.3-MTPLX-Q4` (forge verify: tier *verified*). Merge checked: trained layers differ from v0.2, untouched layers are identical.

### Eval on the 120-task benchmark
| | v0.2 | v0.3 |
|---|---|---|
| Adapter + base 4-bit (mean of 2 runs) | 69.6% (69.2, 70.0) | **75.0%** (74.2, 75.8) |
| Merged → MLX 4-bit | 74.2% | 73.3% |
| GGUF Q4_K_M | 71.7% | 70.0% (C128 70%) |
| MTPLX Q4 | 71.7% | 73.3% (KickAss 58%) |

- The adapter gain (+5.4, both runs, every language) does not carry over to the release formats: mean 72.5% (v0.2) vs 72.2% (v0.3). Note that the v0.2 adapter runs also score below its own merged model, so the adapter comparison overstates the gap.
- New failure in v0.3: `print chr$(147)` **after** poking a character into screen memory, which wipes the result (`poke-char` tasks). With clear-screen: v0.2 1–3 of 8 answers, v0.3 adapter 3–4, MTPLX 6, GGUF 8. Source: v0.3 doubled the samples that poke color registers and then clear the screen (23 → 47), which is correct there but generalizes to poking screen memory.
- Targeted weaknesses, spot-checked at temperature 0 with the training system prompt:
  - Border/background colors: fixed in the v0.3 adapter (v0.2 poked sprite registers), but the MTPLX Q4 pack loses it again.
  - "Clear the screen and print HELLO in yellow" (C64): still `graphic 0 / scnclr 0 / color` (C128 BASIC) in v0.2 and v0.3. The boilerplate strip worked (C128 samples with `graphic 0`: 195 → 25), but `c64_clear_print` kept only 7 of 24 generated samples; 17 clear/yellow C64 samples are not enough to override the base model.
- Decision: by the rule set before training, **v0.2 stays the release** (v0.3 is not better in the formats people run, and adds the clear-after-poke failure). The MTPLX v0.2 pack is serving on port 8000 again.

### Next
1. v0.4 data: many more `c64_clear_print` / `c64_color_print` samples (fix the low yield, aim for ~100), plus C64/C128 samples that poke screen memory with **no** clear-screen afterwards. Then retrain, and judge on the release formats (MTPLX Q4 and GGUF), not only on the adapter.
2. Merge the `checker-fixes` branches in the skillset repos, then pin the commits on `main`.
3. Publish MLX 4-bit, GGUF Q4_K_M and the MTPLX pack on Hugging Face (D1), after approval. The BF16 GGUF (51 GB) is only an intermediate and can be deleted.
4. Phase 2 sources: dataset pipeline (collect → license check → normalize → verify) on the own repos from §1.1.
