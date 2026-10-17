#!/usr/bin/env bash
set -euo pipefail
repo="$(git rev-parse --show-toplevel)"
skill="$repo/.agents/skills/tiktok-storyboard"
for bin in python3 ffmpeg ffprobe; do
  command -v "$bin" >/dev/null || { printf 'Missing executable: %s\n' "$bin" >&2; exit 1; }
done
python3 -m pip install --disable-pip-version-check --no-input --upgrade --target "$skill/.runtime" -r "$skill/requirements-cloud.txt"
export PYTHONPATH="$skill/.runtime${PYTHONPATH:+:$PYTHONPATH}"
python3 -m yt_dlp --version
python3 "$skill/scripts/prepare_asr_model.py" --deps "$skill/.runtime" --models "$skill/.models"
python3 -m unittest discover -s "$skill/tests" -v
