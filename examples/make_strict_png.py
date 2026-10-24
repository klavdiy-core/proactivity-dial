"""Render examples/strict.png from a REAL Claude Code run recorded as stream-json (examples/strict_run.jsonl).

Record your own: claude -p "== ..." --settings <settings with dial.py hooks> --output-format stream-json --verbose
"""
import json
import os
import textwrap

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
PROMPT = "== Output exactly the two characters OK. Absolutely nothing else: no sections, no notes, no lists."
W, PAD, LINE = 1000, 26, 24
BG, FG, DIM, GREEN, YELLOW, CYAN, RED = (24, 26, 33), (220, 223, 228), (120, 126, 140), (120, 200, 120), (230, 200, 110), (110, 190, 230), (235, 120, 110)


def font(names, size):
    for n in names:
        try:
            return ImageFont.truetype(n, size)
        except OSError:
            pass
    return ImageFont.load_default()


MONO, BOLD = font(["consola.ttf", "DejaVuSansMono.ttf"], 17), font(["consolab.ttf", "DejaVuSansMono-Bold.ttf"], 17)


def main():
    events = [json.loads(l) for l in open(os.path.join(HERE, "strict_run.jsonl"), encoding="utf-8") if l.strip()]
    # stream-json does not echo the prompt; the only "user" event is the Stop hook's feedback
    feedback = next(e["message"]["content"] if isinstance(e["message"]["content"], str)
                    else " ".join(c.get("text", "") for c in e["message"]["content"])
                    for e in events if e.get("type") == "user")
    texts = [c["text"].strip() for e in events if e.get("type") == "assistant"
             for c in e["message"].get("content", []) if c.get("type") == "text"]
    rows = [("$ python dial.py set strict      (or start one message with ==)", MONO, DIM), ("", MONO, FG),
            *[(("you:  " if i == 0 else "      ") + l, BOLD, CYAN) for i, l in enumerate(textwrap.wrap(PROMPT, 84))],
            ("", MONO, FG), ("Claude, turn 1:", MONO, DIM)]
    rows += [("  " + l, MONO, GREEN) for l in texts[0].splitlines()]
    rows += [("", MONO, FG), ("the Stop hook does not let the turn end (from the log):", MONO, DIM)]
    rows += [("  " + l, MONO, RED) for l in textwrap.wrap(" ".join(feedback.split()), 88)]
    rows += [("", MONO, FG), ("Claude, turn 2:", MONO, DIM)]
    for l in texts[-1].splitlines():
        rows += [("  " + w, BOLD if "Beyond the ask" in l else MONO, YELLOW if "Beyond the ask" in l else GREEN)
                 for w in (textwrap.wrap(l, 88) or [""])]
    img = Image.new("RGB", (W, PAD * 2 + LINE * len(rows)), BG)
    d = ImageDraw.Draw(img)
    for i, (t, f, c) in enumerate(rows):
        d.text((PAD, PAD + i * LINE), t, font=f, fill=c)
    p = os.path.join(HERE, "strict.png")
    img.save(p)
    print(p, img.size)


if __name__ == "__main__":
    main()
