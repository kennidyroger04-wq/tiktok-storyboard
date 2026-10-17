#!/usr/bin/env python3
"""Download the multilingual tiny CTranslate2 snapshot into an ignored local model cache."""
from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deps", type=Path, default=ROOT / ".runtime")
    parser.add_argument("--models", type=Path, default=ROOT / ".models")
    parser.add_argument("--revision", default="main")
    args = parser.parse_args(argv)
    deps, models = args.deps.resolve(), args.models.resolve()
    deps.mkdir(parents=True, exist_ok=True)
    models.mkdir(parents=True, exist_ok=True)
    os.environ["HF_HOME"] = str(models / "hf-home")
    if deps.is_dir():
        sys.path.insert(0, str(deps))
    try:
        from huggingface_hub import HfApi, snapshot_download
        info = HfApi().model_info("Systran/faster-whisper-tiny", revision=args.revision)
        snapshot = Path(snapshot_download(repo_id="Systran/faster-whisper-tiny", revision=info.sha,
                                          cache_dir=str(models / "hub-cache"))).resolve()
    except Exception as error:
        print(f"Model preparation failed: {error}", file=sys.stderr)
        return 1
    target = models / "faster-whisper-tiny"
    target.mkdir(parents=True, exist_ok=True)
    current = target / "current"
    if current.is_symlink() or current.exists():
        if current.is_dir() and not current.is_symlink():
            print(f"Refusing to replace non-symlink model path: {current}", file=sys.stderr)
            return 1
        current.unlink()
    current.symlink_to(os.path.relpath(snapshot, target), target_is_directory=True)
    manifest = {"repo_id": "Systran/faster-whisper-tiny", "requested_revision": args.revision,
                "resolved_revision": info.sha, "snapshot_path": str(snapshot)}
    (target / "model-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"model": manifest["repo_id"], "revision": info.sha, "path": str(current)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
