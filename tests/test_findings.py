"""Findings from the review of 0.2.0; each test is red on 0.2.0."""
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import dial  # noqa: E402
from test_strict import Base  # noqa: E402

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "dial.py")


def line(kind, content):
    return json.dumps({"type": kind, "message": {"role": kind, "content": content}}) + "\n"


class Findings(Base):
    def test_beyond_the_ask_in_the_middle_of_a_reply_is_not_the_closing_section(self):
        dial.set_level("strict")
        self.prompt("rename foo")
        text = ("Beyond the ask: I will list it below.\n\n" + "Did the rename in utils.py.\n" * 3 +
                "\n## Details\nLots more work here.\n")
        self.assertEqual(self.stop(self.transcript(text))["decision"], "block")

    def test_a_closing_section_with_a_list_still_passes(self):
        dial.set_level("strict")
        self.prompt("rename foo")
        text = "Renamed.\n\n**Beyond the ask:**\n- wanted to fix the typo in bar()\n- assumed tests exist: they did\n"
        self.assertIsNone(self.stop(self.transcript(text)))
        listed = "Renamed.\n\nBeyond the ask:\n- things I left alone:\n  1. the typo\n"     # list items ending in ':'
        self.assertIsNone(self.stop(self.transcript(listed)))
        twice = "Beyond the ask: see the end.\n\n## Work\nRenamed.\n\nBeyond the ask: none.\n"   # the last one closes
        self.assertIsNone(self.stop(self.transcript(twice)))

    def test_only_the_current_turn_counts(self):
        # the previous turn had the section; this turn's reply has no text at all yet
        dial.set_level("strict")
        self.prompt("second ask")
        p = os.path.join(self.tmp.name, "t2.jsonl")
        with open(p, "w", encoding="utf-8") as f:
            f.write(line("user", "first ask"))
            f.write(line("assistant", [{"type": "text", "text": "Done.\n\nBeyond the ask: none."}]))
            f.write(line("user", "second ask"))
            f.write(line("assistant", [{"type": "tool_use", "id": "t", "name": "Read", "input": {}}]))
            f.write(line("user", [{"type": "tool_result", "tool_use_id": "t", "content": "x"}]))
        self.assertEqual(self.stop(p)["decision"], "block")

    def test_tool_results_do_not_start_a_new_turn(self):
        dial.set_level("strict")
        self.prompt("ask")
        p = os.path.join(self.tmp.name, "t3.jsonl")
        with open(p, "w", encoding="utf-8") as f:
            f.write(line("user", "ask"))
            f.write(line("assistant", [{"type": "text", "text": "Done.\n\nBeyond the ask: none."}]))
            f.write(line("assistant", [{"type": "tool_use", "id": "t", "name": "Read", "input": {}}]))
            f.write(line("user", [{"type": "tool_result", "tool_use_id": "t", "content": "x"}]))
        self.assertIsNone(self.stop(p))

    def test_an_unreadable_transcript_is_said_aloud_not_passed_in_silence(self):
        dial.set_level("strict")
        self.prompt("rename foo")
        err = io.StringIO()
        with redirect_stderr(err):
            self.assertIsNone(self.stop(os.path.join(self.tmp.name, "nope.jsonl")))
        self.assertIn("could not read the transcript", err.getvalue())

    def test_get_does_not_create_folders(self):
        d = os.path.join(self.tmp.name, "fresh", "dial")
        os.environ["PROACTIVITY_DIAL_DIR"] = d
        self.assertEqual(dial.get_level(), 1)
        self.prompt("plain")                                 # a normal prompt needs no state either
        self.assertFalse(os.path.exists(d))

    def test_install_is_not_fooled_by_another_tools_dial_py(self):
        s = os.path.join(self.tmp.name, "settings.json")
        with open(s, "w", encoding="utf-8") as f:
            json.dump({"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "python other/dial.py tick"}]}]}},
                      f)
        dial.install(s, script="/x/proactivity-dial/dial.py")
        with open(s, encoding="utf-8") as f:
            cmds = [c["command"] for h in json.load(f)["hooks"]["Stop"] for c in h["hooks"]]
        self.assertEqual(len(cmds), 2)
        self.assertTrue(any(c.endswith('proactivity-dial/dial.py" stop') for c in cmds))
        dial.install(s, script="/x/proactivity-dial/dial.py")            # still idempotent
        with open(s, encoding="utf-8") as f:
            self.assertEqual(len(json.load(f)["hooks"]["Stop"]), 2)

    def test_readme_documents_install_path_and_the_folder_variable(self):
        with open(os.path.join(os.path.dirname(__file__), "..", "README.md"), encoding="utf-8") as f:
            readme = f.read()
        self.assertIn("install <path>", readme)
        self.assertIn("PROACTIVITY_DIAL_DIR", readme)

    def test_cli_get_on_a_fresh_machine_prints_normal(self):
        with tempfile.TemporaryDirectory() as d:
            env = dict(os.environ, PROACTIVITY_DIAL_DIR=os.path.join(d, "none"))
            r = subprocess.run([sys.executable, SCRIPT, "get"], capture_output=True, text=True, env=env)
            self.assertEqual(r.stdout.strip(), "1 (normal)")
            self.assertFalse(os.path.exists(os.path.join(d, "none")))


if __name__ == "__main__":
    unittest.main()
