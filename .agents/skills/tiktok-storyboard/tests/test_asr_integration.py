from __future__ import annotations
import ctypes
import ctypes.util
import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.transcribe_audio import transcribe

MODEL = ROOT / ".models/faster-whisper-tiny/current"
READY = MODEL.is_dir() and ctypes.util.find_library("flite") and ctypes.util.find_library("flite_cmu_us_slt")


@unittest.skipUnless(READY, "requires prepared local tiny ASR model and Flite English voice")
class LocalASRIntegration(unittest.TestCase):
    def test_recognizes_real_synthetic_english_speech_and_aligns_words(self):
        with tempfile.TemporaryDirectory(prefix="storyboard-asr-") as directory:
            root = Path(directory)
            wav = root / "known-speech.wav"
            core = ctypes.CDLL(ctypes.util.find_library("flite"))
            voice_mod = ctypes.CDLL(ctypes.util.find_library("flite_cmu_us_slt"))
            core.flite_init()
            register = voice_mod.register_cmu_us_slt
            register.restype = ctypes.c_void_p
            voice = register(None)
            self.assertTrue(voice)
            speak = core.flite_text_to_speech
            speak.argtypes = (ctypes.c_char_p, ctypes.c_void_p, ctypes.c_char_p)
            speak.restype = ctypes.c_float
            speak(b"Hello world. This is a speech recognition test.", voice, str(wav).encode())
            draft_path = root / "draft.json"
            result = transcribe(wav, draft_path, MODEL, ROOT / ".runtime", language="en", threads=2)
            recognized = " ".join(p["texto"].lower() for p in result["trechos"])
            self.assertIn("hello", recognized)
            self.assertIn("world", recognized)
            words = [w for p in result["trechos"] for w in p.get("palavras", [])]
            self.assertTrue(words)
            self.assertTrue(all(w["inicio"] < w["fim"] for w in words))
            self.assertEqual(result["estado"], "rascunho_nao_verificado")
            self.assertEqual(json.loads(draft_path.read_text())["estado"], "rascunho_nao_verificado")


if __name__ == "__main__":
    unittest.main()
