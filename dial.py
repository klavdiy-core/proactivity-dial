#!/usr/bin/env python3
"""proactivity-dial: tell Claude Code how proactive to be, from "only what I asked" to "proactively insane".

A proactive assistant warns you about steak temperatures you never asked about. Sometimes that is noise; sometimes
the strange tangent is the best idea in the room. This puts the choice on a dial:

  0  quiet      answer only what was asked; no unasked warnings, tips or follow-ups
  1  normal     Claude Code as it is (the dial adds nothing)
  2  curious    after the answer, one short "you didn't ask, but..." note
  3  unhinged   after the answer, three deliberately far-fetched tangents, labelled as such: inspiration on purpose

Set it once (`dial.py set 3`) or for one message with a prefix: `--` quiet, `??` curious, `!!` unhinged.
It works as a UserPromptSubmit hook: it only adds a short note to Claude's context. Standard library only.
"""
import json
import os
import re
import shutil
import sys

__version__ = "0.2.1"
NOTES = {
    0: ("[proactivity-dial: quiet] Answer only what was asked. Add no unasked warnings, safety notes, tips, "
        "alternatives or follow-up offers. If something is truly dangerous, say it in one line at the end."),
    1: "",
    2: ("[proactivity-dial: curious] Answer what was asked first. Then add exactly one short note the user didn't "
        "ask for but would probably want: a risk, a shortcut, or a better question. One, not a list."),
    3: ("[proactivity-dial: unhinged] Answer what was asked first, properly. Then, as a separate block labelled "
        "\"proactively insane:\", give three deliberately far-fetched tangents: one practical, one sideways, one "
        "absurd but oddly useful. Label them clearly so nobody mistakes them for advice. This is for inspiration."),
}
NOTES["strict"] = (
    "[proactivity-dial: strict] Do only what was asked, exactly as asked. If what you find contradicts the "
    "instruction or the user's assumptions, stop and ask before going on: do not quietly change the plan or your "
    "assumptions. End your reply with a section \"Beyond the ask:\" listing what you wanted to do beyond the "
    "request and did not do, and any assumption that turned out wrong (or \"Beyond the ask: none.\").")
PREFIX = {"--": 0, "??": 2, "!!": 3, "==": "strict"}
NAMES = {0: "quiet", 1: "normal", 2: "curious", 3: "unhinged", "strict": "strict"}
BEYOND = re.compile(r"(?im)^[\s*#>_-]*beyond the ask\b")
BLOCK_REASON = ("proactivity-dial strict: end your reply with a \"Beyond the ask:\" section listing what you "
                "wanted to do beyond the request and did not do, and any assumption that turned out wrong "
                "(or \"Beyond the ask: none.\").")


def _dir(create=False):
    """The state folder; created only when something is written (reading the dial leaves no trace)."""
    d = os.environ.get("PROACTIVITY_DIAL_DIR") or os.path.join(os.path.expanduser("~"), ".claude", "proactivity-dial")
    if create:
        os.makedirs(d, exist_ok=True)
    return d


def _parse(v):
    v = str(v).strip().lower()
    return "strict" if v == "strict" else int(v)


def get_level():
    try:
        with open(os.path.join(_dir(), "level"), encoding="utf-8") as f:
            n = _parse(f.read())
        return n if n in NOTES else 1
    except (OSError, ValueError):
        return 1


def set_level(n):
    n = _parse(n)
    if n not in NOTES:
        raise ValueError("the dial goes from 0 to 3, or 'strict'")
    with open(os.path.join(_dir(create=True), "level"), "w", encoding="utf-8") as f:
        f.write(str(n))
    return n


def level_for(prompt):
    head = (prompt or "").lstrip()[:2]
    return PREFIX.get(head, get_level())


def _session_file(session_id, create=False):
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", str(session_id or "default"))[:80]
    d = os.path.join(_dir(), "sessions")
    if create:
        os.makedirs(d, exist_ok=True)
    return os.path.join(d, safe)


def hook(stdin_text):
    """UserPromptSubmit: print the note for this prompt's level (nothing at level 1). Never blocks.
    Remembers per session whether this turn is strict, for the Stop check."""
    try:
        data = json.loads(stdin_text or "{}")
        prompt = data.get("prompt", "")
    except (ValueError, AttributeError):
        return 0
    level = level_for(prompt)
    try:
        flag = _session_file(data.get("session_id"), create=(level == "strict"))
        if level == "strict":
            open(flag, "w").close()
        elif os.path.exists(flag):
            os.remove(flag)
    except OSError:
        pass
    note = NOTES[level]
    if note:
        print(note)
    return 0


def _is_prompt(e, msg):
    """A user line that starts a new turn: the person's own words, not a tool result coming back."""
    if e.get("type") != "user" and msg.get("role") != "user":
        return False
    content = msg.get("content")
    if isinstance(content, str):
        return bool(content.strip())
    return any(isinstance(c, dict) and c.get("type") == "text" for c in content or [])


def _last_assistant_text(transcript_path):
    """The last assistant text of the CURRENT turn only (an earlier turn's reply does not count)."""
    last = ""
    with open(transcript_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                e = json.loads(line)
            except ValueError:
                continue
            msg = e.get("message") or {}
            if _is_prompt(e, msg):
                last = ""
                continue
            if e.get("type") != "assistant" and msg.get("role") != "assistant":
                continue
            content = msg.get("content")
            texts = [content] if isinstance(content, str) else \
                [c.get("text", "") for c in content or [] if isinstance(c, dict) and c.get("type") == "text"]
            text = "\n".join(t for t in texts if t)
            if text.strip():
                last = text
    return last


HEADING = re.compile(r"(?m)^\s*(?![-*+]\s|\d+[.)]\s)(#{1,6}\s|\*\*[^*\n]+\*\*\s*$|[^\n]{1,60}:\s*$)")


def closes_with_beyond(text):
    """The reply ENDS with the section: the last "Beyond the ask" is not followed by another heading."""
    found = list(BEYOND.finditer(text))
    if not found:
        return False
    rest = text[found[-1].end():]
    first_line, _, after = rest.partition("\n")
    return not HEADING.search(after)


def stop_hook(stdin_text):
    """Stop: in a strict turn, the reply must end with a "Beyond the ask:" section, or the turn cannot end.
    Never loops (stop_hook_active), never blocks on its own error."""
    try:
        data = json.loads(stdin_text or "{}")
        if data.get("stop_hook_active") or not os.path.exists(_session_file(data.get("session_id"))):
            return 0
        path = data.get("transcript_path", "")
    except (ValueError, AttributeError, OSError):
        return 0
    try:
        text = _last_assistant_text(path)
    except OSError:
        print(f"proactivity-dial: could not read the transcript ({path!r}); the strict check was not made",
              file=sys.stderr)
        return 0
    if not closes_with_beyond(text):
        print(json.dumps({"decision": "block", "reason": BLOCK_REASON}))
    return 0


def install(settings_path, script=None):
    script = (script or os.path.abspath(__file__)).replace("\\", "/")
    py = "python" if os.name == "nt" else "python3"
    data = {}
    if os.path.exists(settings_path):
        with open(settings_path, encoding="utf-8") as f:
            data = json.load(f)
        shutil.copy2(settings_path, settings_path + ".bak")
    for event, cmd in (("UserPromptSubmit", "hook"), ("Stop", "stop")):
        entries = data.setdefault("hooks", {}).setdefault(event, [])
        command = f'{py} "{script}" {cmd}'
        if not any(c.get("command", "") == command for h in entries for c in h.get("hooks", [])):
            entries.append({"hooks": [{"type": "command", "command": command}]})
    os.makedirs(os.path.dirname(os.path.abspath(settings_path)), exist_ok=True)
    with open(settings_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return settings_path


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    cmd = argv[0] if argv else "get"
    if cmd in ("-h", "--help"):
        print(__doc__ + "\nusage: dial.py get | set 0..3|strict | hook | stop | install [SETTINGS]")
        return 0
    if cmd == "get":
        n = get_level()
        print(n if n == "strict" else f"{n} ({NAMES[n]})")
        return 0
    if cmd == "set":
        try:
            n = set_level(argv[1])
        except (IndexError, ValueError):
            print("usage: dial.py set 0|1|2|3|strict", file=sys.stderr)
            return 2
        print(f"proactivity: {n}" if n == "strict" else f"proactivity: {n} ({NAMES[n]})")
        return 0
    if cmd == "hook":
        return hook(sys.stdin.buffer.read().decode("utf-8", "replace"))
    if cmd == "stop":
        return stop_hook(sys.stdin.buffer.read().decode("utf-8", "replace"))
    if cmd == "install":
        target = argv[1] if len(argv) > 1 else os.path.join(os.path.expanduser("~"), ".claude", "settings.json")
        print(f"installed into {install(target)} (a .bak was left next to it)")
        return 0
    print(f"unknown command {cmd!r}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
