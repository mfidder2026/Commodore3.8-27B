# Commodore3.8-27B

A free, open coding model for Commodore computers (C64, C128, Plus/4 / C16, PET and Amiga;
BASIC and assembler), fine-tuned from [Qwen/Qwen3.8-27B](https://huggingface.co/Qwen/Qwen3.8-27B).
This repository holds the tooling around the model: the verification pipeline, dataset
building, training scripts, evaluation and the engine. See [implement.md](implement.md) for
the full brief and [docs/status.md](docs/status.md) for progress.

> **Disclaimer:** Commodore3.8 is a community project. It is not affiliated with or endorsed
> by the Commodore or Amiga trademark holders.

## Core idea

Facts from manuals go into RAG, style and dialect go into fine-tuning, and correctness
comes from tools. Every training example with code is machine-verified:

```text
source ─▶ syntax checker ─▶ bas2prg / assembler ─▶ VICE (headless, binary monitor) ─▶ expected screen
```

## Setup (macOS, Apple Silicon)

```bash
scripts/fetch_external.sh            # skillset repos with checkers + bas2prg, pinned
uv venv --python 3.12 && uv pip install -e ".[dev]"
```

External tools are auto-detected or set in `toolchain.local.toml` (not committed):

```toml
vice_bin = "/Applications/vice-arm64-gtk3-3.9/bin"
java = "/opt/homebrew/opt/openjdk/bin/java"      # brew install openjdk
kickass_jar = "/path/to/KickAss.jar"              # Kick Assembler 5.x
```

## Verify a program

```bash
.venv/bin/c38-verify hello.bas --lang c64-basic --expect-text "hello"
.venv/bin/c38-verify game.bas  --lang c128-basic --allow-timeout --json
```

Languages: `c64-basic`, `c128-basic`, `plus4-basic`, `pet-basic`, `c64-kickass`.
Exit code 0 = verified, 1 = failed, 2 = incomplete (a required tool is missing).

## Baseline evaluation

Runs the benchmark tasks in `commodore38/eval/tasks/` against any OpenAI-compatible server
(MTPLX on `:8000`, LM Studio on `:1234`, llama-server, Ollama):

```bash
.venv/bin/c38-eval --base-url http://127.0.0.1:8000/v1 --model <model-id> --variant bare
.venv/bin/c38-eval --base-url http://127.0.0.1:8000/v1 --model <model-id> --variant skills-loop
```

## License

Code in this repository: Apache-2.0 (see [LICENSE](LICENSE)). The model is a derivative of
Qwen3.8-27B (Apache-2.0); see [NOTICE](NOTICE).
