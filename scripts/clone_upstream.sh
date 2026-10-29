#!/usr/bin/env bash
# Clone the three upstream model repos at the exact commits this project was
# run against, into repos/. They are deliberately not vendored into this
# repository — see docs/setup.md.
#
# The only local change made to any of them is the Dose-CLIP.pth symlink in
# FoundDiff, which this script recreates.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p repos

clone_at() {
  local name="$1" url="$2" sha="$3"
  if [ -d "repos/$name/.git" ]; then
    echo "[skip] repos/$name already exists"
    return
  fi
  echo "[clone] $name <- $url @ $sha"
  git clone "$url" "repos/$name"
  git -C "repos/$name" checkout --quiet "$sha"
}

clone_at CoreDiff  https://github.com/qgao21/CoreDiff.git  9bc31dc1d6184a880bd6334db34c466569a3642a
clone_at FoundDiff https://github.com/hao1635/FoundDiff.git c85a3a0e87ae2e4587650f0fb7efc15f3311d8e2
clone_at NEED      https://github.com/qgao21/NEED.git       5d023278deeefb3872c7519b5d985fb4b19948a2

# src/DADiff.py does torch.load('Dose-CLIP.pth') with a path relative to the
# FoundDiff repo root, so the real checkpoint is linked into place.
if [ -f "weights/FoundDiff/DA-CLIP.pth" ]; then
  ln -sfn "$ROOT/weights/FoundDiff/DA-CLIP.pth" "repos/FoundDiff/Dose-CLIP.pth"
  echo "[link] repos/FoundDiff/Dose-CLIP.pth -> weights/FoundDiff/DA-CLIP.pth"
else
  echo "[warn] weights/FoundDiff/DA-CLIP.pth missing; download it first (docs/setup.md)"
fi

echo "done."
