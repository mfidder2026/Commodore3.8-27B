---
license: apache-2.0
base_model: Qwen/Qwen3.8-27B
language:
  - en
  - nl
tags:
  - code
  - commodore
  - c64
  - c128
  - basic
  - 6502
  - kick-assembler
  - retrocomputing
  - mlx
  - gguf
  - mtplx
pipeline_tag: text-generation
---

# Commodore3.8-27B

A free coding model for Commodore 8-bit computers: **C64 BASIC V2, C128 BASIC 7.0 and
6502 assembler (Kick Assembler)**. It is a fine-tune of
[Qwen/Qwen3.8-27B](https://huggingface.co/Qwen/Qwen3.8-27B).

> **Disclaimer:** Commodore3.8 is a community project. It is not affiliated with or endorsed
> by the Commodore or Amiga trademark holders.

## What it does differently from the base model

Asked for a C64 program, stock Qwen3.8-27B writes plausible code that rarely runs on
real hardware conventions. It uses UPPERCASE listings, statements from other BASIC
dialects (`ELSE`, `MOD`, `WHILE`) and assembler syntax from other assemblers. This model was
trained only on programs that passed a full machine check:

```text
syntax checker ─▶ bas2prg / Kick Assembler ─▶ VICE emulator (headless) ─▶ expected screen or memory
```

Conventions it follows:
- BASIC listings in **lowercase**, ready for `bas2prg -i` / `petcat`. PETSCII control characters
  are written as `chr$(…)`, so a listing is plain ASCII and copy-paste safe.
- No statements from other dialects: in C64 code no `else`, `mod`, `graphic` or `sqrt`.
- Assembler in Kick Assembler syntax with a BASIC upstart.

## Evaluation

Commodore-Eval v1: 120 tasks (56 C64 BASIC, 40 C128 BASIC, 24 Kick Assembler). Every
answer is built and run in VICE and checked against a known result. One attempt, no
documentation in the prompt, thinking off, temperature 0.2.

| | Qwen3.8-27B | Commodore3.8-27B v0.2 |
|---|---|---|
| C64 BASIC | 7% | 75% |
| C128 BASIC | 0% | 80% |
| Kick Assembler | 0% | 46–62% |
| **All 120 tasks** | **3%** | **72–74%** |
| Passes the syntax checker | 31% | 93% |

The ranges come from the release formats (MLX 4-bit 74%, GGUF Q4_K_M 72%, MTPLX 72%). They
are within run-to-run noise of each other. One run at temperature 0.2 varies by about
±5 points.

## Files and how to run them

| Format | Size | For |
|---|---|---|
| MLX 4-bit (group 32) | 16 GB | LM Studio (MLX), `mlx_lm.server`, Apple Silicon |
| GGUF Q4_K_M | 16 GB | LM Studio, Ollama, llama.cpp |
| MTPLX pack (4-bit body, native MTP head) | 20 GB | [MTPLX](https://github.com/youssofal/MTPLX), ~33 tok/s on an M3 Max (≈1.75× plain MLX) |
| bf16 safetensors | 52 GB | further fine-tuning and conversion |

**Turn thinking off** (`enable_thinking: false` in the chat template). The model was
trained and evaluated that way. Example request:

```json
{"messages": [{"role": "user", "content": "Write a C64 BASIC V2 program that clears the screen and prints HELLO in yellow."}],
 "temperature": 0.2, "chat_template_kwargs": {"enable_thinking": false}}
```

The answer is a single fenced code block.

## Training

- **Data:** synthetic and verified. Tasks come from parametrized families (sums, loops,
  strings, screen and color memory, sprites, BASIC 7.0 statements, 6502 arithmetic, tables,
  macros), each with a computed expected result. The teacher was Qwen3.8-27B with the
  Commodore skill documents and up to three rounds of checker/emulator feedback. Only answers
  that passed the full pipeline were kept. The stored samples contain only a short system
  prompt, so the model behaves like the skill-guided teacher without needing the
  documents. The training families are disjoint from the benchmark, and samples are
  decontaminated against benchmark prompts and reference solutions.
- **v0.2:** 877 samples (790 train / 87 validation).
- **Recipe:** QLoRA with mlx-lm on a 4-bit MLX conversion, LoRA rank 16 / scale 2.0 on the
  last 16 of 64 blocks (29M trainable parameters). Loss only on the answer, 2 epochs,
  effective batch 4, lr 1e-4 cosine, trained locally on a Mac (M3 Max, 128 GB).
- **Merge:** the LoRA deltas are added to the original bf16 shards. The vision tower and
  MTP head are unchanged from Qwen3.8-27B.

## Limitations

- Knowledge gaps remain: sprite setup, interrupt (raster IRQ) code and some C128 functions
  (`dec`) are error-prone. Check programs in an emulator.
- C64 and C128 only for now. Plus/4, PET and Amiga are planned but not trained.
- Long free-form programs (games, demos) are outside the training distribution, which
  consists of short, checkable tasks.
- The MTP head was not fine-tuned. This affects only speculative-decoding speed, never the
  output: drafts are verified by the main model.

## License

Apache-2.0, as the base model. Commodore3.8-27B is a fine-tune of Qwen/Qwen3.8-27B by
the Qwen team (Alibaba Cloud). Modifications: LoRA fine-tuning on verified Commodore BASIC
and assembler data, merged into the base weights and re-quantized. See `NOTICE`.

Tooling, verification pipeline and benchmark:
[github.com/mfidder2026/Commodore3.8-27B](https://github.com/mfidder2026/Commodore3.8-27B).
