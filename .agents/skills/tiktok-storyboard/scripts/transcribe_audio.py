#!/usr/bin/env python3
"""Create an explicitly unreviewed local faster-whisper transcript with word timestamps."""
from __future__ import annotations
import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNTIME = ROOT / ".runtime"
DEFAULT_MODEL = ROOT / ".models/faster-whisper-tiny/current"


class TranscriptionError(RuntimeError):
    pass


def media_info(path: Path) -> tuple[float, bool]:
    try:
        p = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)], check=True, capture_output=True, text=True)
    except (FileNotFoundError, subprocess.CalledProcessError) as error:
        raise TranscriptionError(f"Could not probe media: {error}") from error
    data = json.loads(p.stdout)
    duration = float(data.get("format", {}).get("duration") or 0)
    return duration, any(s.get("codec_type") == "audio" for s in data.get("streams", []))


def silence_gaps(phrases: list[dict], duration: float, minimum: float = 0.35) -> list[dict]:
    gaps, cursor = [], 0.0
    for phrase in sorted(phrases, key=lambda p: p["inicio"]):
        start = max(0.0, min(duration, float(phrase["inicio"])))
        end = max(start, min(duration, float(phrase["fim"])))
        if start - cursor >= minimum:
            gaps.append({"inicio": round(cursor, 3), "fim": round(start, 3), "tipo": "lacuna_sem_fala_detectada"})
        cursor = max(cursor, end)
    if duration - cursor >= minimum:
        gaps.append({"inicio": round(cursor, 3), "fim": round(duration, 3), "tipo": "lacuna_sem_fala_detectada"})
    return gaps


def transcribe(source: Path, output: Path, model_dir: Path = DEFAULT_MODEL, deps: Path = DEFAULT_RUNTIME,
               language: str | None = None, threads: int = 4) -> dict:
    if not source.is_file():
        raise TranscriptionError(f"Input file does not exist: {source}")
    if not model_dir.is_dir():
        raise TranscriptionError(f"Local ASR model is missing: {model_dir}; run prepare_asr_model.py")
    if threads < 1:
        raise TranscriptionError("threads must be at least 1")
    duration, has_audio = media_info(source)
    if not has_audio:
        raise TranscriptionError("Input has no audio stream; no transcript was produced")
    if deps.is_dir():
        sys.path.insert(0, str(deps.resolve()))
    try:
        from faster_whisper import WhisperModel
    except ImportError as error:
        raise TranscriptionError(f"faster-whisper is not installed in {deps}") from error
    try:
        with tempfile.TemporaryDirectory(prefix="tiktok-storyboard-audio-") as temporary:
            wav = Path(temporary) / "audio.wav"
            subprocess.run(["ffmpeg", "-hide_banner", "-v", "error", "-xerror", "-i", str(source),
                            "-map", "0:a:0", "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", "-y", str(wav)],
                           check=True, capture_output=True, text=True)
            model = WhisperModel(str(model_dir.resolve()), device="cpu", compute_type="int8", cpu_threads=threads, num_workers=1)
            segments, info = model.transcribe(str(wav), language=language, task="transcribe", beam_size=5,
                                              vad_filter=True, condition_on_previous_text=False, word_timestamps=True)
            phrases = []
            for segment in segments:
                text = segment.text.strip()
                if not text or getattr(segment, "no_speech_prob", 0.0) >= 0.6:
                    continue
                words = []
                for word in getattr(segment, "words", None) or []:
                    word_text = str(getattr(word, "word", "")).strip()
                    if not word_text:
                        continue
                    prob = getattr(word, "probability", None)
                    words.append({"inicio": round(float(word.start), 3), "fim": round(float(word.end), 3),
                                  "texto": word_text, "probabilidade": round(float(prob), 4) if prob is not None else None})
                uncertain = [w["texto"] for w in words if w["probabilidade"] is not None and w["probabilidade"] < 0.35]
                avg = float(segment.avg_logprob)
                phrases.append({"inicio": round(float(segment.start), 3), "fim": round(float(segment.end), 3),
                                "locutor": None, "texto": text, "avg_logprob": avg,
                                "no_speech_prob": float(segment.no_speech_prob), "palavras": words,
                                "incerto": avg < -0.8 or bool(uncertain), "palavras_incertas": uncertain})
    except subprocess.CalledProcessError as error:
        raise TranscriptionError((error.stderr or error.stdout or str(error))[-1500:]) from error
    except Exception as error:
        raise TranscriptionError(f"Local transcription failed: {error}") from error
    result = {"estado": "rascunho_nao_verificado", "idioma": getattr(info, "language", None),
              "probabilidade_idioma": getattr(info, "language_probability", None),
              "metodo": "faster-whisper tiny multilingual local, CPU int8, VAD e alinhamento por palavra; revisão auditiva obrigatória",
              "fonte": str(source.resolve()), "duracao_segundos": duration, "trechos": phrases,
              "silencios_estimados": silence_gaps(phrases, duration),
              "limitacoes": ["ASR automático não revisado; não use como transcrição exata sem conferir todo o áudio.",
                             "Locutores não são diarizados; campos sem rótulo permanecem desconhecidos."]}
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_suffix(output.suffix + ".tmp")
    temp.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(output)
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("media", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--deps", type=Path, default=DEFAULT_RUNTIME)
    parser.add_argument("--language", choices=("pt", "en"))
    parser.add_argument("--threads", type=int, default=4)
    args = parser.parse_args(argv)
    try:
        result = transcribe(args.media, args.output, args.model_dir, args.deps, args.language, args.threads)
        print(json.dumps({"status": result["estado"], "language": result["idioma"],
                          "segments": len(result["trechos"]), "output": str(args.output)}, ensure_ascii=False))
        return 0
    except TranscriptionError as error:
        print(f"Transcription unavailable: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
