#!/usr/bin/env bash
# Run Commodore-Eval (bare variant, thinking off) against an MLX model served by
# mlx_lm.server, optionally with a LoRA adapter. Base and adapter go through the
# same server and weights, so the comparison is fair.
#
#   scripts/eval_mlx.sh <name> <model-path> [adapter-path]
#   scripts/eval_mlx.sh 9b-base    models/qwen3.5-9b-mlx-4bit
#   scripts/eval_mlx.sh 9b-adapter models/qwen3.5-9b-mlx-4bit adapters/proefrun-v0.1-9b
set -euo pipefail

cd "$(dirname "$0")/.."
name="$1" model="$2" adapter="${3:-}"
port="${C38_EVAL_PORT:-8080}"

args=(--model "$model" --port "$port")
[ -n "$adapter" ] && args+=(--adapter-path "$adapter")
.venv-train/bin/python -m mlx_lm server "${args[@]}" > "runs/mlx-server-$name.log" 2>&1 &
server=$!
trap 'kill $server 2>/dev/null; wait $server 2>/dev/null || true' EXIT

for _ in $(seq 1 150); do
  curl -s -m 2 "http://127.0.0.1:$port/v1/models" > /dev/null && break
  sleep 2
done

# caffeinate: an idle Mac sleeps and stalls the eval overnight
caffeinate -i .venv/bin/c38-eval --base-url "http://127.0.0.1:$port/v1" --model default_model \
  --variant bare --no-think --out "runs/eval-$name"
