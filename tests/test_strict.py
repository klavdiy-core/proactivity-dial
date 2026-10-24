import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import dial  # noqa: E402


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["PROACTIVITY_DIAL_DIR"] = self.tmp.name

    def tearDown(self):
        os.environ.pop("PROACTIVITY_DIAL_DIR", None)
        self.tmp.cleanup()

    def prompt(self, text, session="s1"):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(dial.hook(json.dumps({"hook_event_name": "UserPromptSubmit", "prompt": text,
                                                   "session_id": session})), 0)
        return out.getvalue().strip()

    def transcript(self, *assistant_texts):
        p = os.path.join(self.tmp.name, "t.jsonl")
        with open(p, "w", encoding="utf-8") as f:
            f.write(json.dumps({"type": "user", "message": {"role": "user", "content": "do X"}}) + "\n")
            for t in assistant_texts:
                f.write(json.dumps({"type": "assistant", "message": {"role": "assistant",
                                                                     "content": [{"type": "text", "text": t}]}}) + "\n")
        return p

    def stop(self, transcript, session="s1", active=False):
        out = io.StringIO()
        with redirect_stdout(out):
            code = dial.stop_hook(json.dumps({"hook_event_name": "Stop", "session_id": session,
                                              "transcript_path": transcript, "stop_hook_active": active}))
        self.assertEqual(code, 0)
        s = out.getvalue().strip()
        return json.loads(s) if s else None


class StrictNote(Base):
    def test_strict_note_says_only_the_ask_stop_on_mismatch_and_list_the_rest(self):
        dial.set_level("strict")
        note = self.prompt("rename foo to bar in utils.py")
        self.assertIn("only what was asked", note.lower())
        self.assertIn("stop and ask", note.lower())
        self.assertIn("Beyond the ask:", note)

    def test_strict_by_name_and_get_shows_it(self):
        dial.set_level("strict")
        self.assertEqual(dial.get_level(), "strict")
        out = io.StringIO()
        with redirect_stdout(out):
            dial.main(["get"])
        self.assertIn("strict", out.getvalue())

    def test_prefix_makes_one_message_strict(self):
        self.assertIn("Beyond the ask:", self.prompt("== rename foo"))
        self.assertEqual(self.prompt("rename foo"), "")


class StrictStop(Base):
    def test_a_strict_turn_without_the_list_cannot_end(self):
        self.prompt("== rename foo to bar")
        r = self.stop(self.transcript("Renamed foo to bar and also tidied the imports."))
        self.assertEqual(r["decision"], "block")
        self.assertIn("Beyond the ask:", r["reason"])

    def test_with_the_list_it_ends(self):
        self.prompt("== rename foo to bar")
        self.assertIsNone(self.stop(self.transcript("Renamed foo to bar.\n\nBeyond the ask: none.")))
        self.assertIsNone(self.stop(self.transcript("Done.\n\n**Beyond the ask:**\n- tidy imports (not done)")))

    def test_only_the_last_message_counts(self):
        self.prompt("== rename foo")
        r = self.stop(self.transcript("Beyond the ask: none.", "Then I also refactored utils.py."))
        self.assertEqual(r["decision"], "block")

    def test_never_loops(self):
        self.prompt("== rename foo")
        self.assertIsNone(self.stop(self.transcript("no list here"), active=True))

    def test_non_strict_turns_are_left_alone(self):
        self.prompt("rename foo")
        self.assertIsNone(self.stop(self.transcript("no list here")))

    def test_a_one_message_prefix_does_not_stick_to_the_next_turn(self):
        self.prompt("== rename foo")
        self.prompt("now explain it")
        self.assertIsNone(self.stop(self.transcript("no list here")))

    def test_strict_is_per_session(self):
        self.prompt("== rename foo", session="a")
        self.prompt("rename foo", session="b")
        self.assertIsNone(self.stop(self.transcript("no list"), session="b"))
        self.assertEqual(self.stop(self.transcript("no list"), session="a")["decision"], "block")

    def test_a_missing_or_broken_transcript_never_blocks(self):
        self.prompt("== rename foo")
        self.assertIsNone(self.stop(os.path.join(self.tmp.name, "nope.jsonl")))
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(dial.stop_hook("not json"), 0)


class InstallBoth(Base):
    def test_install_adds_the_stop_hook_too(self):
        settings = os.path.join(self.tmp.name, "settings.json")
        dial.install(settings, script="/opt/dial.py")
        dial.install(settings, script="/opt/dial.py")
        with open(settings) as f:
            s = json.load(f)
        stops = [c["command"] for h in s["hooks"]["Stop"] for c in h["hooks"]]
        self.assertEqual(len(stops), 1)
        self.assertTrue(stops[0].endswith("stop"))


if __name__ == "__main__":
    unittest.main()
