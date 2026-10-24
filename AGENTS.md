# Instructions for agents

This repo writes to the backup memory of a physical camera over service-mode
USB. Mistakes here cost hardware, not a git branch.

## Non-negotiable rules

1. **`recon` before any write.** The `recon` log is the only rollback record
   that exists. Without it there is no way back.
2. **Do not write without probing.** `probe-pdt` confirms the path works on
   that specific body. Which path is open **varies by model** — see
   `docs/protocol-findings.md`.
3. **Validate the reads before writing.** All 35 language bytes must be `01`
   or `02`. Any other value means the addresses do not line up on that body:
   stop, do not write.
4. **Do not read `Error: Cannot overwrite backup` as a failure.** It is a
   known false positive. The verification reads are the truth.
5. **Do not use `bk w` on recent bodies** without checking it works. On the
   ZV-E10 II it returns `error 129` on all 35 addresses.
6. **Never send `0` to the `tweak` menu** unless applying is the intent: `0`
   means "apply", not "exit". The menu cannot be left cleanly over a pipe,
   which is what the `lang` command is for.
7. **Feature modes take `stock` or `unlock`, never `on`/`off`.** "Recording
   limit on" is ambiguous about whether the limit or the tweak is on, and
   getting it backwards writes the opposite of what was asked. If you add a
   feature, keep this vocabulary.
8. **For the recording-limit tweaks, trust the read over the table.** Bodies
   from ~2019 on never had the 29:59 cap, so the table's "stock" is not their
   stock. Writing it would *impose* a limit that was never there.

## What an agent cannot do

Some steps need a person at the camera. Do not simulate them or report them
as done:

- Putting the camera in mass storage mode from its physical menu.
- Plugging in the USB-C cable.
- Pulling the battery for the power cycle or to recover a session.
- Typing the `sudo` password. macOS caches the credential **per tty**, so a
  `sudo -v` in another terminal does not help. The pattern that works in
  Claude Code is for the person to launch the script with the `!` prefix while
  the agent reads the output.

## Before calling anything done

Compare the bytes read against the target byte for byte and state the count.
Do not settle for "looks like it worked":

```python
after == target        # not "Success" appearing in the output
```

## Layout

```
scripts/feed.py       generates service-shell commands; region + feature tables
scripts/run.sh        driver: detects the camera, asks for sudo, pipes, logs
scripts/detect.sh     waits for the camera to appear and describes it
scripts/install.sh    clones PMCA-RE, applies the patch, builds the venv
patches/              the 'lang' command against upstream a82f5ba
docs/                 protocol findings and troubleshooting
logs/                 the real session, serial number sanitised
```

## When touching `feed.py`

Modes split into those that write and those that do not. If you add one, say
which explicitly in the docstring and in the README table. A mode that writes
while presenting itself as safe is the worst possible bug in this repo.

## When sharing logs

Logs carry the body's `Serial number` and `Product code`. Sanitise before
publishing:

```bash
sed -E 's/^(Serial number:|Product code:)([[:space:]]*).*/\1\2<redacted>/'
```
