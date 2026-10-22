#!/usr/bin/env bash
# Usage: bash deploy/push_to_space.sh <huggingface-username> [space-name]
# Needs: `hf auth login --add-to-git-credential` done once, and a Space created (see README).
set -euo pipefail
HF_USER="${1:?Usage: push_to_space.sh <huggingface-username> [space-name]}"
SPACE="${2:-flexproof-ai}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
git -C "$REPO_ROOT" archive HEAD | tar -x -C "$TMP"
cp "$REPO_ROOT/deploy/space_README.md" "$TMP/README.md"
cd "$TMP"
git init -q -b main
git add -A
git -c user.name="$(git -C "$REPO_ROOT" config user.name)" -c user.email="$(git -C "$REPO_ROOT" config user.email)" commit -q -m "Deploy FlexProof AI"
git push --force "https://huggingface.co/spaces/$HF_USER/$SPACE" main
echo "Pushed. Build logs: https://huggingface.co/spaces/$HF_USER/$SPACE"
echo "Live app: https://${HF_USER,,}-$SPACE.hf.space"
