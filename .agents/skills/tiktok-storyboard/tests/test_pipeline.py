from __future__ import annotations
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.inspect_video import InspectionError, inspect
from scripts.storyboard import MapError, main as board_main, render, validate_map
from scripts.transcribe_audio import TranscriptionError, silence_gaps, transcribe


class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="storyboard-tests-")
        cls.root = Path(cls.temp.name)
        cls.video = cls.root / "two-scenes.mp4"
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "color=c=red:s=160x90:r=10:d=1",
            "-f", "lavfi", "-i", "color=c=blue:s=160x90:r=10:d=1",
            "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=16000:duration=2",
            "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]", "-map", "[v]", "-map", "2:a:0",
            "-t", "2", "-c:v", "mpeg4", "-c:a", "aac", str(cls.video)], check=True, capture_output=True)
        cls.inspection = inspect(cls.video, cls.root / "inspection", interval=0.5, max_samples=10)
        cls.frame = Path(cls.inspection["samples"][0]["frame"])
        cls.frame = cls.root / "inspection" / cls.frame

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.out = self.root / self._testMethodName
        self.out.mkdir(exist_ok=True)
        (self.out / "anchor.jpg").write_bytes(self.frame.read_bytes())

    def sample_map(self):
        return {"schema_version": 1, "fonte": {"arquivo": "synthetic.mp4"},
            "video": {"duracao_segundos": 2.0}, "contagens": {"segmentos_observados": 2},
            "segmentos": [
                {"id": "S01", "inicio": 0.0, "fim": 1.0, "ancora_ids": ["A01"], "descricao": "quadro vermelho"},
                {"id": "S02", "inicio": 1.0, "fim": 2.0, "ancora_ids": ["A02"], "descricao": "quadro azul"}],
            "ancoras": [{"id": "A01", "quadro": "anchor.jpg", "timestamp_extracao": 0.0},
                        {"id": "A02", "quadro": "anchor.jpg", "timestamp_extracao": 1.0}],
            "transcricao": {"estado": "audio_inacessivel", "trechos": []}, "limitacoes": []}

    def write_map(self, data):
        path = self.out / "mapa.json"
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return path

    def test_01_video_metadata_and_full_decode(self):
        self.assertEqual(self.inspection["status"], "decoded")
        self.assertEqual(self.inspection["decode_check"], "complete")
        self.assertEqual(self.inspection["video"]["width"], 160)
        self.assertTrue(self.inspection["video"]["audio_present"])

    def test_02_samples_cover_start_and_end(self):
        samples = self.inspection["samples"]
        self.assertEqual(samples[0]["timestamp"], 0.0)
        self.assertGreaterEqual(samples[-1]["timestamp"], 1.9)
        self.assertTrue(all((self.root / "inspection" / x["frame"]).is_file() for x in samples))

    def test_03_scene_change_candidate_detected(self):
        self.assertTrue(self.inspection["detected_cuts"])

    def test_04_contact_sheet_written(self):
        self.assertTrue((self.root / "inspection" / "contact-sheet.html").is_file())
        persisted = json.loads((self.root / "inspection" / "inspection.json").read_text())
        self.assertEqual(persisted["video"], self.inspection["video"])

    def test_06_invalid_video_rejected(self):
        bad = self.root / "invalid.mp4"
        bad.write_text("not media")
        with self.assertRaises(InspectionError):
            inspect(bad, self.out, 1, max_samples=10)

    def test_07_missing_video_rejected(self):
        with self.assertRaises(InspectionError):
            inspect(self.root / "missing.mp4", self.out, 1, max_samples=10)

    def test_08_bad_interval_rejected(self):
        with self.assertRaises(InspectionError):
            inspect(self.video, self.out, 0, max_samples=10)

    def test_09_sampling_over_limit_rejected(self):
        with self.assertRaises(InspectionError):
            inspect(self.video, self.out, .01, max_samples=5)

    def test_10_valid_scene_map(self):
        self.assertEqual(len(validate_map(self.sample_map(), self.out / "mapa.json")), 2)

    def test_11_map_rejects_gap(self):
        d = self.sample_map(); d["segmentos"][1]["inicio"] = 1.2
        with self.assertRaisesRegex(MapError, "gap or overlap"):
            validate_map(d, self.out / "mapa.json")

    def test_12_map_rejects_overlap(self):
        d = self.sample_map(); d["segmentos"][1]["inicio"] = .8
        with self.assertRaisesRegex(MapError, "gap or overlap"):
            validate_map(d, self.out / "mapa.json")

    def test_13_map_requires_full_duration(self):
        d = self.sample_map(); d["segmentos"][-1]["fim"] = 1.9
        with self.assertRaisesRegex(MapError, "video duration"):
            validate_map(d, self.out / "mapa.json")

    def test_14_unknown_anchor_rejected(self):
        d = self.sample_map(); d["segmentos"][0]["ancora_ids"] = ["A99"]
        with self.assertRaisesRegex(MapError, "unknown anchor"):
            validate_map(d, self.out / "mapa.json")

    def test_15_missing_anchor_file_rejected(self):
        d = self.sample_map(); d["ancoras"][0]["quadro"] = "missing.jpg"
        with self.assertRaisesRegex(MapError, "missing or escapes"):
            validate_map(d, self.out / "mapa.json")

    def test_16_path_traversal_rejected(self):
        d = self.sample_map(); d["ancoras"][0]["quadro"] = "../../etc/passwd"
        with self.assertRaisesRegex(MapError, "missing or escapes"):
            validate_map(d, self.out / "mapa.json")

    def test_17_html_escapes_and_anchors_resolve(self):
        d = self.sample_map(); d["segmentos"][0]["descricao"] = "<script>alert(1)</script>"
        path = self.write_map(d); page_path, _ = render(d, path)
        page = page_path.read_text()
        self.assertIn("&lt;script&gt;", page)
        self.assertNotIn("<script>alert", page)
        class Images(HTMLParser):
            def __init__(self): super().__init__(); self.src = []
            def handle_starttag(self, tag, attrs):
                if tag == "img": self.src.append(dict(attrs)["src"])
        parser = Images(); parser.feed(page)
        self.assertEqual(len(parser.src), 2)
        self.assertTrue(all((page_path.parent / x).is_file() for x in parser.src))

    def test_18_integrated_visual_and_prompt_fields_render(self):
        d = self.sample_map(); d["segmentos"][0].update({"observado": "pessoa observada", "inferido": "interior provável",
            "movimentos": "levanta a mão", "movimento_camera": "panorâmica curta", "efeitos_sonoros": ["batida"],
            "prompt_imagem": "recriar cartela e cor", "prompt_animacao": "mover o personagem", "continuidade": "camisa azul"})
        path = self.write_map(d); page, _ = render(d, path); text = page.read_text()
        for value in ("pessoa observada", "interior provável", "levanta a mão", "panorâmica curta", "batida", "recriar cartela", "mover o personagem", "camisa azul"):
            self.assertIn(value, text)

    def test_19_transcript_splits_across_scenes_using_word_times(self):
        d = self.sample_map(); d["transcricao"] = {"estado": "revisada", "trechos": [{"inicio": .7, "fim": 1.3,
            "texto": "Oi tudo bem", "palavras": [{"inicio": .7, "fim": .85, "texto": "Oi"},
            {"inicio": .9, "fim": 1.05, "texto": "tudo"}, {"inicio": 1.1, "fim": 1.3, "texto": "bem"}]}]}
        path = self.write_map(d); page, _ = render(d, path); html_text = page.read_text()
        self.assertIn("Oi tudo", html_text); self.assertIn("bem", html_text)
        self.assertEqual(html_text.count("Oi tudo bem"), 0)

    def test_20_reviewed_transcript_exports_txt_srt_json_aliases(self):
        d = self.sample_map(); d["transcricao"] = {"estado": "revisada", "idioma": "pt-BR", "trechos": [{"inicio": .1, "fim": .4, "texto": "Olá!"}]}
        path = self.write_map(d); render(d, path)
        for ext in ("txt", "srt", "json"):
            pt = (self.out / f"transcricao.{ext}").read_text(); en = (self.out / f"transcript.{ext}").read_text()
            self.assertEqual(pt, en)
        self.assertIn("Olá!", (self.out / "transcript.txt").read_text())

    def test_21_unreviewed_transcript_never_exports_final_text(self):
        d = self.sample_map(); d["transcricao"] = {"estado": "rascunho_nao_verificado", "trechos": [{"inicio": .1, "fim": .4, "texto": "draft"}]}
        path = self.write_map(d); render(d, path)
        self.assertFalse((self.out / "transcript.txt").exists())

    def test_22_word_outside_phrase_rejected(self):
        d = self.sample_map(); d["transcricao"] = {"estado": "revisada", "trechos": [{"inicio": .2, "fim": .5, "texto": "x", "palavras": [{"inicio": .1, "fim": .3, "texto": "x"}]}]}
        with self.assertRaisesRegex(MapError, "outside phrase"):
            validate_map(d, self.out / "mapa.json")

    def test_23_speech_free_gaps_are_estimates(self):
        self.assertEqual(len(silence_gaps([{"inicio": 1, "fim": 2}], 4)), 2)

    def test_24_transcriber_missing_model_fails_explicitly(self):
        with self.assertRaisesRegex(TranscriptionError, "model is missing"):
            transcribe(self.video, self.out / "draft.json", self.root / "none", self.root / "deps")

    def test_25_cli_check_validates_map(self):
        path = self.write_map(self.sample_map())
        self.assertEqual(board_main([str(path), "--check"]), 0)


if __name__ == "__main__":
    unittest.main()
