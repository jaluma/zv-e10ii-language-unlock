# CLAUDE.md

See [AGENTS.md](AGENTS.md) — this repo's working rules live there and apply
the same.

There is also a skill in `.claude/skills/zve10-language-unlock/` with the full
step-by-step procedure.

## One-line summary

Writes the backup properties of a Japanese Sony ZV-E10 II — the 35 language
bytes, plus the PAL/NTSC selector and the recording limits — through service
mode's PDT path, because the per-property path (`bk w`) returns `error 129` on
this body.
