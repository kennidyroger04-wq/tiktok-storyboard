# TikTok Storyboard

Skill for downloading public TikTok videos or processing local video files, inspecting the complete timeline, drafting local speech recognition, and building a reusable audiovisual storyboard.

The installed Codex skill is in `.agents/skills/tiktok-storyboard/`. The legacy uploaded folder and ZIP remain untouched for provenance; the install script, tests, and dependencies below apply to the installed skill.

## Cloud setup

Requires Python 3, FFmpeg, and ffprobe. From the repository root:

```bash
bash .agents/skills/tiktok-storyboard/install-cloud.sh
```

This installs pinned direct Python dependencies into the skill's ignored `.runtime/`, downloads the `faster-whisper-tiny` multilingual model into ignored `.models/`, and runs the test suite. No paid API or credential is needed. The tiny model is downloaded on first setup and is not stored in Git. `yt-dlp` uses the environment's OS trust store for TLS verification.

## Use

For a public TikTok URL:

```bash
SKILL=.agents/skills/tiktok-storyboard
PYTHONPATH="$SKILL/.runtime" python3 "$SKILL/scripts/download_public.py" 'https://www.tiktok.com/@creator/video/123' --output "$PWD/work/123"
```

Then fully decode and sample the video:

```bash
python3 "$SKILL/scripts/inspect_video.py" work/123/VIDEO.mp4 --output work/123/inspection --interval 2
```

For local media, start with `inspect_video.py` directly. The recognizer produces a **draft**, not verified verbatim copy:

```bash
PYTHONPATH="$SKILL/.runtime" python3 "$SKILL/scripts/transcribe_audio.py" work/123/VIDEO.mp4 --output work/123/transcript-draft.json --language pt
```

Review the audio and correct the word-level draft before marking a transcript reviewed. Create a `mapa.json` following [the delivery schema](.agents/skills/tiktok-storyboard/references/entrega.md), then validate and render:

```bash
python3 "$SKILL/scripts/storyboard.py" outputs/123/mapa.json --check
python3 "$SKILL/scripts/storyboard.py" outputs/123/mapa.json
```

The renderer writes integrated HTML and Markdown, and TXT/SRT/JSON transcript exports only when the transcript is marked reviewed. See [SKILL.md](.agents/skills/tiktok-storyboard/SKILL.md) for evidence, copyright, privacy, and visual review requirements. Generated media, model files, and dependencies belong in ignored work/output/runtime locations, not Git.

## Tests and audit

```bash
PYTHONPATH=.agents/skills/tiktok-storyboard/.runtime python3 -m unittest discover -s .agents/skills/tiktok-storyboard/tests -v
```

The suite includes synthetic video and English speech fixtures; speech integration is conditional on the local model and Flite voice. Recovery history, real TikTok download/inspection evidence, limitations, and test counts are documented in [AUDITORIA.md](AUDITORIA.md).
