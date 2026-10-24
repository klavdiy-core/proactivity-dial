# proactivity-dial

Tell Claude Code how proactive to be, from "only what I asked" to "proactively insane".

> RU: «проблема проактивного ИИ в том, что иногда он проактивно безумен» — да. А иногда это безумие и есть лучшая идея в комнате. Регулятор от «только то, что спросил» до «проактивно безумно», где безумие — по заказу и с пометкой.

## What hurts, and what doesn't

You ask about a $60 steak and get an unasked lecture on mechanically tenderized beef and USDA 145°F. That's proactive AI being proactively insane. But the same reflex, aimed on purpose, is a brainstorming partner: the tangent you'd never have thought of. The problem isn't the madness. It's that you don't get to choose when.

## The dial

| level | name | what Claude does |
|---|---|---|
| 0 | quiet | answers only what was asked; no unasked warnings, tips, alternatives or follow-up offers (a truly dangerous thing still gets one line at the end) |
| 1 | normal | Claude Code as it is; the dial adds nothing |
| 2 | curious | after the answer, exactly **one** note you didn't ask for but would probably want |
| 3 | unhinged | after the answer, a block labelled **"proactively insane:"** with three deliberately far-fetched tangents: one practical, one sideways, one absurd but oddly useful |

```sh
python dial.py set 3        # stays until you change it
python dial.py get
```

Or turn it for **one message**, with a prefix:

```
-- how long do I rest a steak?          quiet, just the answer
?? rename this function                  one side note
!! ideas for a birthday dinner           three labelled tangents
```

It works as a `UserPromptSubmit` hook: it adds one short note to Claude's context for that message, never blocks anything, and stays silent at level 1. Standard library only, Python 3.8+.

## Install

```sh
curl -O https://raw.githubusercontent.com/klavdiy-core/proactivity-dial/main/dial.py
python dial.py install          # adds the hook to ~/.claude/settings.json (your other hooks stay; a .bak is left)
```

## Limits

- It asks; it doesn't force. The note goes into Claude's context like any instruction, and the model may still drift, especially over a long session.
- A prefix only counts at the very start of the message, so `why does a -- b fail?` stays a normal question.
- The level is one per machine (`~/.claude/proactivity-dial/level`), not per project.

## Test

```sh
python -m unittest discover -s tests
```

Default silence, each level's note, the level surviving between prompts, prefixes working for one message only and only at the start, a broken level file falling back to normal, the range check, garbage input never blocking, and an install that keeps your other hooks. Every check here was broken on purpose to see a test go red.

## License

MIT
