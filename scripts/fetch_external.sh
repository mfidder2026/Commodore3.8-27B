#!/usr/bin/env bash
# Fetch the skillset repos (checkers, bas2prg, skill documents) at pinned commits.
# Bump a pin deliberately: verification results depend on the checker version.
set -euo pipefail

cd "$(dirname "$0")/.."
mkdir -p external

fetch() {
  local name="$1" commit="$2"
  local dir="external/$name"
  if [ ! -d "$dir/.git" ]; then
    git clone -q "https://github.com/mfidder2026/$name" "$dir"
  fi
  git -C "$dir" fetch -q origin
  git -C "$dir" checkout -q "$commit"
  echo "$name @ $commit"
}

fetch c64_kickass_ai_skillset ca1fbe17383eeb0d858a8d0ff1f642574c58f4b7
fetch c128_basic_ai_skillset  ba191adff0552bb3f0da4358ffbfb673cabc30f9
fetch c64_basic_ai_skillset   9b442a7c2d4c9dbde4093469df51e1ea2d116206
