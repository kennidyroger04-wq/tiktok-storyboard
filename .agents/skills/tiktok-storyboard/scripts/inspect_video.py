#!/usr/bin/env python3
"""Decode a video and create time-spaced frames, scene-change candidates, and a contact sheet."""
from __future__ import annotations

import argparse
import html
import json
import math
import re
import subprocess
import sys
from fractions import Fraction
from pathlib import Path


class InspectionError(RuntimeError):
    pass


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(args, check=True, capture_output=True, text=True)
    except FileNotFoundError as error:
        raise InspectionError(f"Required executable unavailable: {args[0]}") from error
    except subprocess.CalledProcessError as error:
        detail = (error.stderr or error.stdout or str(error)).strip()
        raise InspectionError(detail[-2000:]) from error


def inspect(source: Path, output: Path, interval: float = 2.0,
            scene_threshold: float = 0.35, max_samples: int = 1000) -> dict:
    source, output = source.resolve(), output.resolve()
    if not source.is_file():
        raise InspectionError(f"Input video does not exist: {source}")
    if not math.isfinite(interval) or interval <= 0 or max_samples < 2:
        raise InspectionError("interval must be positive and max_samples at least 2")
    probe = json.loads(_run([
        "ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(source)
    ]).stdout)
    videos = [s for s in probe.get("streams", []) if s.get("codec_type") == "video"]
    if not videos:
        raise InspectionError("Input contains no video stream")
    stream = videos[0]
    duration = float(probe.get("format", {}).get("duration") or stream.get("duration") or 0)
    if duration <= 0 or not math.isfinite(duration):
        raise InspectionError("Could not determine a positive video duration")
    if math.ceil(duration / interval) + 1 > max_samples:
        raise InspectionError("Sampling would exceed max_samples; increase --interval")
    output.mkdir(parents=True, exist_ok=True)
    frames_dir = output / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    # Include both the first and final decodable frames, even when the interval does not divide duration.
    times = [i * interval for i in range(math.ceil(duration / interval)) if i * interval < duration]
    try:
        fps = float(Fraction(stream.get("avg_frame_rate") or "0/1"))
    except (ValueError, ZeroDivisionError):
        fps = 0.0
    # Container duration can extend beyond the video stream due to an AAC tail.
    # Seek to the final video-frame time rather than the overall container duration.
    video_duration = float(stream.get("duration") or duration)
    final_time = max(0.0, video_duration - (1.0 / fps if fps > 0 else 0.001))
    if not times or final_time - times[-1] > 0.05:
        times.append(final_time)
    samples = []
    for index, stamp in enumerate(times):
        frame = frames_dir / f"sample-{index:04d}.jpg"
        _run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{stamp:.6f}",
              "-i", str(source), "-frames:v", "1", "-q:v", "2", "-pix_fmt", "yuvj420p", "-y", str(frame)])
        if not frame.is_file() or frame.stat().st_size == 0:
            raise InspectionError(f"Could not extract frame at {stamp:.3f}s")
        samples.append({"timestamp": round(stamp, 3), "frame": str(frame.relative_to(output))})
    # Scene scores are candidates only. The full decode and uniform samples remain authoritative for coverage.
    log = _run(["ffmpeg", "-hide_banner", "-i", str(source), "-vf",
                f"select='gt(scene,{scene_threshold})',showinfo", "-vsync", "vfr", "-q:v", "3",
                "-y", str(frames_dir / "cut-%04d.jpg")])
    raw_cuts = []
    cut_frames = sorted(frames_dir.glob("cut-*.jpg"))
    for index, match in enumerate(re.finditer(r"pts_time:([0-9.]+)", log.stderr)):
        stamp = float(match.group(1))
        cut = {"timestamp": round(stamp, 3), "candidate": True}
        if index < len(cut_frames):
            cut["frame"] = str(cut_frames[index].relative_to(output))
        raw_cuts.append(cut)
    # One hard cut can trigger neighboring-frame scores. Coalesce them to a single candidate.
    cuts = []
    for cut in raw_cuts:
        if cuts and cut["timestamp"] - cuts[-1]["timestamp"] <= 0.5:
            continue
        cuts.append(cut)
    _run(["ffmpeg", "-hide_banner", "-v", "error", "-xerror", "-i", str(source), "-f", "null", "-"])
    report = {
        "status": "decoded", "decode_check": "complete", "source": str(source),
        "video": {"duration": duration, "width": int(stream["width"]), "height": int(stream["height"]),
                  "fps": stream.get("avg_frame_rate"), "codec": stream.get("codec_name"),
                  "audio_present": any(s.get("codec_type") == "audio" for s in probe.get("streams", []))},
        "samples": samples, "detected_cuts": cuts, "scene_threshold": scene_threshold,
        "coverage": {"start": samples[0]["timestamp"], "last_sample": samples[-1]["timestamp"],
                     "duration": duration, "uniform_interval": interval},
    }
    (output / "inspection.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    cards = []
    for item in samples:
        src = html.escape(Path(item["frame"]).as_posix(), quote=True)
        cards.append(f'<figure><img loading="lazy" src="{src}" alt="Quadro em {item["timestamp"]} s"><figcaption>{item["timestamp"]:.3f} s</figcaption></figure>')
    page = ('<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>Folha de contato</title><style>body{font:16px system-ui;margin:1rem}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:1rem}img{width:100%;height:auto}figure{margin:0}</style>'
            '<h1>Folha de contato — cobertura temporal</h1><div class="grid">' + ''.join(cards) + '</div></html>')
    (output / "contact-sheet.html").write_text(page, encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("media", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--interval", type=float, default=2.0)
    parser.add_argument("--scene-threshold", type=float, default=0.35)
    parser.add_argument("--max-samples", type=int, default=1000)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(inspect(args.media, args.output, args.interval, args.scene_threshold, args.max_samples),
                         ensure_ascii=False, indent=2))
        return 0
    except (InspectionError, OSError, json.JSONDecodeError) as error:
        print(f"Inspection failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
