"""Merge an mlx-lm LoRA adapter into the original Hugging Face checkpoint.

`mlx_lm fuse` writes an MLX-shaped checkpoint: other weight names, no vision
tower, no MTP head, a rewritten config. That is fine for MLX but not as the
published model or as input for llama.cpp's convert_hf_to_gguf.py. This script
adds W += scale * (lora_a @ lora_b).T to the original bf16 shards instead, so
every other file and tensor stays byte-for-byte the original.

The adapter can be trained on a quantized MLX conversion of the same model:
the LoRA matrices are float and the linear layers keep the HF layout (checked
against `mlx_lm fuse`: equal up to bf16 rounding).

  .venv-train/bin/python -m commodore38.train.merge_hf \\
      --base ~/.cache/huggingface/hub/models--Qwen--Qwen3.8-27B/snapshots/<rev> \\
      --adapter adapters/v0.2 --out models/commodore3.8-27b-v0.2
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import mlx.core as mx

# mlx-lm module path prefix -> HF tensor name prefix
MLX_PREFIX = "language_model.model."
HF_PREFIX = "model.language_model."


def lora_deltas(adapter: Path) -> dict[str, mx.array]:
    """HF weight name -> float32 delta for every LoRA-wrapped linear layer."""
    config = json.loads((adapter / "adapter_config.json").read_text())
    if config.get("fine_tune_type", "lora") != "lora":
        raise SystemExit(f"only plain LoRA adapters are supported, not {config['fine_tune_type']}")
    scale = config["lora_parameters"]["scale"]
    weights = mx.load(str(adapter / "adapters.safetensors"))
    deltas = {}
    for key, a in weights.items():
        if not key.endswith(".lora_a"):
            continue
        module = key[: -len(".lora_a")]
        if not module.startswith(MLX_PREFIX):
            raise SystemExit(f"unexpected adapter key {key}")
        b = weights[module + ".lora_b"]
        delta = (scale * (a.astype(mx.float32) @ b.astype(mx.float32))).T
        deltas[HF_PREFIX + module[len(MLX_PREFIX):] + ".weight"] = delta
    return deltas


def merge(base: Path, adapter: Path, out: Path) -> int:
    deltas = lora_deltas(adapter)
    weight_map = json.loads((base / "model.safetensors.index.json").read_text())["weight_map"]
    missing = sorted(set(deltas) - set(weight_map))
    if missing:
        raise SystemExit(f"adapter targets tensors that are not in the base model: {missing[:5]}")

    out.mkdir(parents=True, exist_ok=False)
    shards_to_patch = {weight_map[name] for name in deltas}
    for path in sorted(base.iterdir()):
        if path.name in shards_to_patch:
            tensors, metadata = mx.load(str(path), return_metadata=True)
            for name, tensor in tensors.items():
                if name in deltas:
                    tensors[name] = (tensor.astype(mx.float32) + deltas[name]).astype(tensor.dtype)
            mx.save_safetensors(str(out / path.name), tensors, metadata=metadata)
            print(f"patched {path.name}")
        elif path.name == "crc32.txt":
            continue  # checksums of the original shards, wrong after patching
        elif path.is_file():
            shutil.copy2(path, out / path.name)  # follows the HF-cache symlinks
    print(f"merged {len(deltas)} LoRA layers into {out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--base", type=Path, required=True, help="original HF checkpoint directory")
    p.add_argument("--adapter", type=Path, required=True, help="mlx-lm adapter directory")
    p.add_argument("--out", type=Path, required=True, help="new directory for the merged checkpoint")
    args = p.parse_args(argv)
    return merge(args.base.expanduser(), args.adapter, args.out)


if __name__ == "__main__":
    raise SystemExit(main())
