#!/usr/bin/env python3
"""Validate a reviewed scene map and render an integrated, offline HTML/Markdown storyboard."""
from __future__ import annotations

import argparse
import html
import json
import math
import os
import sys
from pathlib import Path
from urllib.parse import quote


class MapError(ValueError):
    pass


def number(value, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise MapError(f"{name} must be a finite number")
    return float(value)


def validate_map(data: dict, map_path: Path) -> list[dict]:
    if not isinstance(data, dict):
        raise MapError("map root must be an object")
    video, segments, anchors = data.get("video"), data.get("segmentos"), data.get("ancoras")
    if not isinstance(video, dict) or not isinstance(segments, list) or not segments:
        raise MapError("video and a non-empty segmentos array are required")
    if not isinstance(anchors, list):
        raise MapError("ancoras must be an array")
    duration = number(video.get("duracao_segundos"), "video.duracao_segundos")
    if duration <= 0:
        raise MapError("video duration must be positive")
    root = map_path.resolve().parent
    by_id = {}
    for i, anchor in enumerate(anchors):
        if not isinstance(anchor, dict) or not isinstance(anchor.get("id"), str) or not anchor["id"]:
            raise MapError(f"ancoras[{i}] requires an id")
        if anchor["id"] in by_id:
            raise MapError(f"duplicate anchor id: {anchor['id']}")
        frame = anchor.get("quadro")
        if not isinstance(frame, str) or not frame:
            raise MapError(f"anchor {anchor['id']} requires quadro")
        resolved = (root / frame).resolve()
        if root not in resolved.parents or not resolved.is_file():
            raise MapError(f"anchor {anchor['id']} frame missing or escapes output directory")
        stamp = number(anchor.get("timestamp_extracao"), f"anchor {anchor['id']} timestamp")
        if not 0 <= stamp <= duration:
            raise MapError(f"anchor {anchor['id']} timestamp outside duration")
        by_id[anchor["id"]] = anchor
    normalized, cursor, seen = [], 0.0, set()
    for i, item in enumerate(segments):
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"]:
            raise MapError(f"segmentos[{i}] requires an id")
        if item["id"] in seen:
            raise MapError(f"duplicate segment id: {item['id']}")
        seen.add(item["id"])
        start = number(item.get("inicio"), f"segment {item['id']} inicio")
        end = number(item.get("fim"), f"segment {item['id']} fim")
        if end <= start:
            raise MapError(f"segment {item['id']} has non-positive duration")
        if abs(start - cursor) > 0.001:
            raise MapError(f"temporal gap or overlap before {item['id']}: expected {cursor:.3f}, got {start:.3f}")
        anchor_ids = item.get("ancora_ids", [])
        if not isinstance(anchor_ids, list) or any(a not in by_id for a in anchor_ids):
            raise MapError(f"segment {item['id']} references unknown anchor")
        normalized.append({**item, "inicio": start, "fim": end, "ancora_ids": anchor_ids})
        cursor = end
    if abs(cursor - duration) > 0.001:
        raise MapError(f"segments end at {cursor:.3f}s; video duration is {duration:.3f}s")
    transcript = data.get("transcricao")
    if transcript is not None:
        if not isinstance(transcript, dict):
            raise MapError("transcricao must be an object")
        states = {"revisada", "rascunho_nao_verificado", "sem_fala", "audio_inacessivel",
                  "reproducao_integral_indisponivel"}
        if transcript.get("estado") not in states:
            raise MapError("unknown transcript state")
        phrases = transcript.get("trechos", [])
        if not isinstance(phrases, list):
            raise MapError("transcricao.trechos must be an array")
        for i, phrase in enumerate(phrases):
            if not isinstance(phrase, dict) or not isinstance(phrase.get("texto"), str):
                raise MapError(f"transcript phrase {i} requires text")
            if transcript["estado"] == "revisada" and not phrase["texto"].strip():
                raise MapError(f"reviewed phrase {i} cannot be empty")
            start, end = number(phrase.get("inicio"), f"phrase {i} inicio"), number(phrase.get("fim"), f"phrase {i} fim")
            if not 0 <= start < end <= duration:
                raise MapError(f"phrase {i} interval outside video duration")
            words = phrase.get("palavras", [])
            if not isinstance(words, list):
                raise MapError(f"phrase {i} palavras must be an array")
            for j, word in enumerate(words):
                if not isinstance(word, dict) or not isinstance(word.get("texto"), str):
                    raise MapError(f"word {i}.{j} requires text")
                ws, we = number(word.get("inicio"), f"word {i}.{j} inicio"), number(word.get("fim"), f"word {i}.{j} fim")
                if not start <= ws < we <= end:
                    raise MapError(f"word {i}.{j} outside phrase interval")
    return normalized


def srt_time(seconds: float) -> str:
    ms = round(seconds * 1000)
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def render(data: dict, map_path: Path, html_path: Path | None = None) -> tuple[Path, Path]:
    segments = validate_map(data, map_path)
    root = map_path.resolve().parent
    anchors = {a["id"]: a for a in data["ancoras"]}
    transcript = data.get("transcricao", {})
    phrases = sorted(transcript.get("trechos", []), key=lambda p: float(p["inicio"]))
    cards, timeline = [], []

    def section(label, value):
        if value is None or value == "" or value == [] or value == {}:
            return ""
        if isinstance(value, (list, dict)):
            value = json.dumps(value, ensure_ascii=False, indent=2)
        return f"<section><h3>{html.escape(label)}</h3><pre>{html.escape(str(value))}</pre></section>"

    for scene in segments:
        anchor_cards = []
        for aid in scene["ancora_ids"]:
            anchor = anchors[aid]
            frame = Path(anchor["quadro"])
            src = quote(Path(os.path.relpath(root / frame, (html_path or root / "storyboard.html").resolve().parent)).as_posix(), safe="/.")
            anchor_cards.append(f'<figure><img loading="lazy" src="{html.escape(src, quote=True)}" alt="Âncora {html.escape(aid)}"><figcaption>{html.escape(aid)} — {float(anchor["timestamp_extracao"]):.3f} s</figcaption></figure>')
        dialogue = []
        for phrase in phrases:
            overlap_start = max(float(phrase["inicio"]), scene["inicio"])
            overlap_end = min(float(phrase["fim"]), scene["fim"])
            if overlap_start >= overlap_end:
                continue
            words = phrase.get("palavras", [])
            shown = " ".join(w["texto"] for w in words if float(w["inicio"]) < scene["fim"] and float(w["fim"]) > scene["inicio"]) if words else phrase["texto"]
            continuation = overlap_start > float(phrase["inicio"]) or overlap_end < float(phrase["fim"])
            who = phrase.get("locutor") or "locutor não identificado"
            flag = " · revisar incerteza" if phrase.get("incerto") else ""
            dialogue.append(f'<p class="dialogue"><strong>{html.escape(who)} {float(phrase["inicio"]):.3f}–{float(phrase["fim"]):.3f} s{html.escape(flag)}</strong><br>{html.escape(shown)}<small>Sobreposição nesta cena: {overlap_start:.3f}–{overlap_end:.3f} s{" · fala contínua na cena seguinte/anterior" if continuation else ""}</small></p>')
        if not dialogue:
            dialogue = ["<p>Sem diálogo associado a esta cena.</p>"]
        description = scene.get("observado", scene.get("descricao", "Descrição não fornecida"))
        cards.append(
            f'<article><header><h2>{html.escape(scene["id"])}</h2><p>{scene["inicio"]:.3f}–{scene["fim"]:.3f} s · {scene["fim"]-scene["inicio"]:.3f} s</p></header>'
            + '<div class="frames">' + ''.join(anchor_cards) + '</div>'
            + f'<p><strong>Observado:</strong> {html.escape(str(description))}</p>'
            + section("Inferência", scene.get("inferido"))
            + section("Ações e movimentos", scene.get("movimentos", scene.get("movimento")))
            + section("Movimento de câmera", scene.get("movimento_camera"))
            + section("Texto na tela", scene.get("texto_na_tela"))
            + '<section><h3>Diálogo literal / trecho ASR</h3>' + ''.join(dialogue) + '</section>'
            + section("Áudio e efeitos sonoros", scene.get("efeitos_sonoros", scene.get("audio")))
            + section("Prompt de imagem — sugestão de reconstrução", scene.get("prompt_imagem"))
            + section("Prompt de animação — sugestão de reconstrução", scene.get("prompt_animacao"))
            + section("Continuidade visual", scene.get("continuidade"))
            + section("Sugestão criativa", scene.get("sugestao_criativa")) + '</article>'
        )
        timeline.append(f"- {scene['id']} ({scene['inicio']:.3f}–{scene['fim']:.3f}s): {description}")

    html_out = html_path or root / "storyboard.html"
    html_out.parent.mkdir(parents=True, exist_ok=True)
    page = ('<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Storyboard audiovisual</title>'
            '<style>body{font:16px/1.5 system-ui,sans-serif;max-width:1100px;margin:2rem auto;padding:0 1rem;color:#202124}article{border:1px solid #bbb;border-radius:.6rem;padding:1rem;margin:1rem 0}.frames{display:flex;gap:1rem;flex-wrap:wrap}figure{margin:0;max-width:360px}img{width:auto;max-width:100%;max-height:420px}section{border-top:1px solid #ddd;margin-top:.8rem;padding-top:.3rem}pre{white-space:pre-wrap;background:#f6f7f8;padding:.7rem}.dialogue{background:#f4f7ff;padding:.7rem;border-left:3px solid #5680cc}.dialogue small{display:block;color:#555}</style></head><body><h1>Storyboard audiovisual integrado</h1>' + ''.join(cards) + '</body></html>')
    html_out.write_text(page, encoding="utf-8")
    md = ["# Mapa do vídeo", "", f"Duração: {data['video']['duracao_segundos']} s", "", "## Linha do tempo", "", *timeline, "", "## Âncoras", ""]
    for a in data["ancoras"]:
        md.append(f"- {a['id']} — `{a['quadro']}`, timestamp {a['timestamp_extracao']} s; {a.get('descricao_visual', 'descrição pendente')}")
    md.extend(["", "## Transcrição", "", f"Estado: {transcript.get('estado', 'não informado')}"])
    for phrase in phrases:
        md.append(f"- {float(phrase['inicio']):.3f}–{float(phrase['fim']):.3f} s — {phrase.get('locutor') or 'locutor não identificado'}: {phrase['texto']}")
    for key, title in (("limitacoes", "Limitações"),):
        if data.get(key):
            md.extend(["", f"## {title}", "", *[f"- {x}" for x in data[key]]])
    md_path = root / "mapa-do-video.md"
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")
    if transcript.get("estado") == "revisada" and phrases:
        txt = []
        srt = []
        for i, phrase in enumerate(phrases, 1):
            line = f"{phrase.get('locutor') + ': ' if phrase.get('locutor') else ''}{phrase['texto']}"
            txt.append(f"[{float(phrase['inicio']):.3f}–{float(phrase['fim']):.3f}] {line}")
            srt.append(f"{i}\n{srt_time(float(phrase['inicio']))} --> {srt_time(float(phrase['fim']))}\n{line}")
        json_text = json.dumps({"estado": "revisada", "idioma": transcript.get("idioma"), "trechos": phrases,
                                "silencios": transcript.get("silencios_estimados", transcript.get("silencios", []))}, ensure_ascii=False, indent=2) + "\n"
        for name, text in (("transcricao.txt", "\n".join(txt)+"\n"), ("transcript.txt", "\n".join(txt)+"\n"),
                           ("transcricao.srt", "\n\n".join(srt)+"\n"), ("transcript.srt", "\n\n".join(srt)+"\n"),
                           ("transcricao.json", json_text), ("transcript.json", json_text)):
            (root / name).write_text(text, encoding="utf-8")
    return html_out, md_path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mapa", type=Path)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--html", type=Path)
    args = parser.parse_args(argv)
    try:
        data = json.loads(args.mapa.read_text(encoding="utf-8"))
        validate_map(data, args.mapa)
        if args.check:
            print("JSON válido; cenas cobrem toda a duração e âncoras existem.")
        else:
            paths = render(data, args.mapa, args.html)
            print("Gerados: " + " e ".join(map(str, paths)))
        return 0
    except (OSError, json.JSONDecodeError, MapError) as error:
        print(f"Storyboard inválido: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
