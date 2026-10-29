#!/usr/bin/env bash
# Build a verified MTPLX pack (4-bit body, bf16 MTP head) from a merged HF checkpoint.
#
#   scripts/build_mtplx.sh <merged-hf-dir> <pack-name>
#   scripts/build_mtplx.sh models/commodore3.8-27b-v0.2 Commodore3.8-27B-v0.2-MTPLX-Q4
#
# MTPLX 2.12.2 `forge build` converts the body fine but its MTP contract calibration
# fails for Qwen3.8-27B from bf16, also on the untouched official weights (it tests
# no contract candidates). The contract below is the one stamped on the working
# Youssofal/Qwen3.8-27B-MTPLX-Optimized-Speed pack, same architecture and MTP head;
# `forge verify` then measures it and stamps the pack only if the rows pass.
set -euo pipefail

cd "$(dirname "$0")/.."
src="$(cd "$1" && pwd)" name="$2"
pack="$HOME/.mtplx/models/$name"
recipe="$(python3 -c 'import json; print(json.dumps(json.load(open("train/mtplx/recipe-optimized-speed.json"))))')"
mkdir -p runs/forge

caffeinate -i mtplx forge build --repo "$src" --out runs/forge --run-id "$name" \
  --recipe "$recipe" --branded-name "$name" > "runs/forge-$name.log" 2>&1 || true
verdict="$(python3 -c "import json; print(json.load(open('runs/forge/$name/build_outcome.json'))['verdict'])")"
case "$verdict" in
  contract_calibration_failed) echo "forge: conversion done, calibration failed as expected; setting the contract" ;;
  *) echo "forge verdict: $verdict"; [ -f "$pack/mtplx_runtime.json" ] && exit 0 ;;
esac

python3 - "$pack/config.json" <<'EOF'
import json, sys
path = sys.argv[1]
config = json.load(open(path))
config["mtplx_mtp_contract"] = {
    "base_hidden_variant": "post_norm", "concat_order": "embedding_hidden",
    "hidden_variant": "post_norm", "mtp_position_mode": "local",
    "mtp_quant_group_size": 64, "mtp_quant_mode": "affine",
}
json.dump(config, open(path, "w"), indent=2)
EOF

caffeinate -i mtplx forge verify "$pack" --stamp --out runs/forge --run-id "$name-stamp" \
  --source-repo "Qwen/Qwen3.8-27B + Commodore3.8 LoRA (local merge of $src)" > "runs/forge-stamp-$name.log" 2>&1
mtplx inspect "$pack" | grep -E "tier|message"
