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

    def hook(self, prompt):
        out = io.StringIO()
        with redirect_stdout(out):
            code = dial.hook(json.dumps({"hook_event_name": "UserPromptSubmit", "prompt": prompt}))
        self.assertEqual(code, 0)
        return out.getvalue().strip()


class Levels(Base):
    def test_default_is_silent(self):
        self.assertEqual(dial.get_level(), 1)
        self.assertEqual(self.hook("how long do I rest a steak?"), "")

    def test_quiet_forbids_unasked_warnings(self):
        dial.set_level(0)
        note = self.hook("how long do I rest a steak?")
        self.assertIn("only what was asked", note)
        self.assertIn("unasked", note)

    def test_curious_adds_one_side_note(self):
        dial.set_level(2)
        note = self.hook("rename this function")
        self.assertIn("one", note.lower())
        self.assertIn("didn't ask", note)

    def test_unhinged_asks_for_three_labelled_tangents(self):
        dial.set_level(3)
        note = self.hook("plan a birthday dinner")
        self.assertIn("three", note)
        self.assertIn("proactively insane", note)
        self.assertIn("label", note.lower())

    def test_level_survives_between_prompts(self):
        dial.set_level(3)
        self.assertIn("proactively insane", self.hook("a"))
        self.assertIn("proactively insane", self.hook("b"))


class PerPrompt(Base):
    def test_prefix_overrides_for_one_prompt_only(self):
        dial.set_level(1)
        self.assertIn("proactively insane", self.hook("!! ideas for a cat cafe"))
        self.assertEqual(self.hook("ideas for a cat cafe"), "")
        self.assertIn("only what was asked", self.hook("-- what is 2+2"))
        self.assertIn("didn't ask", self.hook("?? fix the typo"))

    def test_prefix_inside_the_text_is_ignored(self):
        self.assertEqual(self.hook("why does `a -- b` fail?"), "")


class Robust(Base):
    def test_bad_level_file_falls_back_to_normal(self):
        with open(os.path.join(self.tmp.name, "level"), "w") as f:
            f.write("banana")
        self.assertEqual(dial.get_level(), 1)
        self.assertEqual(self.hook("hi"), "")

    def test_set_rejects_out_of_range(self):
        with self.assertRaises(ValueError):
            dial.set_level(7)

    def test_garbage_input_never_blocks(self):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(dial.hook("not json"), 0)


class Install(Base):
    def test_install_merges_and_is_idempotent(self):
        settings = os.path.join(self.tmp.name, "settings.json")
        with open(settings, "w") as f:
            json.dump({"model": "x", "hooks": {"UserPromptSubmit": [{"hooks": [{"type": "command",
                                                                               "command": "mine.sh"}]}]}}, f)
        dial.install(settings, script="/opt/dial.py")
        dial.install(settings, script="/opt/dial.py")
        with open(settings) as f:
            s = json.load(f)
        cmds = [c["command"] for h in s["hooks"]["UserPromptSubmit"] for c in h["hooks"]]
        self.assertEqual(sum("dial.py" in c for c in cmds), 1)
        self.assertIn("mine.sh", cmds)
        self.assertEqual(s["model"], "x")


if __name__ == "__main__":
    unittest.main()
