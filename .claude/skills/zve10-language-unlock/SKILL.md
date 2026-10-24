---
name: zve10-language-unlock
description: Unlock menu languages and hidden features (PAL/NTSC selector, recording limits) on a Sony domestic-market camera by writing backup properties over service-mode USB with Sony-PMCA-RE. Use when someone has a Sony ZV-E10 II, A7, A6xxx, ZV-1, FX30 or other grey import with no language option in the menu, when they want 25p/50p out of a 60Hz-locked body, or when they hit "Senser adjust control error 129", "No tweaks available" or "Cannot overwrite backup".
---

# Sony domestic-market camera unlock

Bodies sold on the Japanese domestic market ship with a single menu language
and no language item at all. This skill writes the camera's backup properties
over service-mode USB.

## Before touching anything

**Pin the actual model.** People mistype these — "EZ-10 mark 2" is a
`ZV-E10 II` (`ZV-E10M2`). If it matches no real model, ask before proceeding.

**Say what is lost.** This writes into the region and calibration data area:
any official Sony service option is gone. A Japanese warranty is
domestic-only anyway.

**The free route exists.** Do not recommend paid services before checking
service mode. And do not confuse PMCA-RE's two routes:

- **App mode** (*PlayMemories Camera Apps*, *OpenMemories: Tweak*): dead on
  2018+ bodies, needs the Android PMCA subsystem.
- **Service mode** (`serviceshell`): **independent of that subsystem**, works
  on 2024 bodies.

Confusing them leads to saying "there is no way", which is false.

## What you cannot do yourself

Ask the person to do these and wait for confirmation:

1. Put the camera in mass storage mode: `MENU > Setup > USB >
   USB Connection Mode > Mass Storage` (Japanese: `セットアップ > USB >
   USB接続モード > マスストレージ`).
2. Connect it over USB-C and quit Photos, Image Capture, Dropbox and Drive.
3. Pull the battery for ~10 s when the time comes.
4. Run the commands under `sudo`. macOS caches the credential **per tty**, so
   `sudo -v` from another terminal does not help: have them launch the script
   with the `!` prefix and read the output yourself.

## Procedure

### 1. Build the environment

```bash
brew install python@3.11 libusb git      # 3.11 on purpose: requirements pin
git clone https://github.com/ma1co/Sony-PMCA-RE.git     # pycparser==2.17
cd Sony-PMCA-RE && python3.11 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
```

Run **from source**: the published binaries (v0.18, April 2022) lag `master`.

### 2. Check the camera is on the bus

**Do not use `system_profiler SPUSBDataType`**: on recent macOS it returns
zero devices with the camera connected and working.

```bash
ioreg -p IOUSB -l -w 0 | grep -E '"USB Product Name"|"idVendor"|"bInterfaceClass"'
# idVendor 1356 = 0x054C (Sony);  bInterfaceClass 8 = Mass Storage
```

### 3. Recon — read-only, mandatory

The 35 language properties sit at `0x010d008f`..`0x010d00b1`, one byte each,
`01` = enabled, `02` = disabled.

```
> info                    # confirms model and region (e.g. CX89300_J1)
> bk r 0x010d008f         # ... all 35, incrementing by one
```

**Save this output: it is the only rollback record.** The `>` prompt ends up
glued to the value (`>01`); strip it when parsing.

If any value is neither `01` nor `02`, **stop**: the addresses do not line up
on that body.

### 4. Probe which write path works

This is the crux. **Which path is open depends on the body**, and there is no
way to know without testing:

| Path | Command | A7 IV | ZV-E10 II |
|---|---|---|---|
| per-property `BACKUP_WRITE` | `bk w` | works | **error 129** |
| PDT (whole blob) | `bk patch`, `tweak`, `lang` | fails | **works** |

Probe PDT by rewriting the value already there — identical content, full path
exercised:

```
> bk patch 0x010d0090 01
Success
```

### 5. Write

The PDT path clears the per-property protection bit (`attr & 1`), which is
exactly what `bk w` does not do and the cause of `error 129`.

- All 35 languages: `tweak` → the language tweak's number → `0`.
- A specific pattern: apply the `lang` command patch from
  `jaluma/zv-e10ii-language-unlock` and write the 35 bytes in one go.

For the ZV-E10 II, **recommend the `CEC` (Europe) pattern** over all 35: it
includes English and Spanish and leaves Chinese off, whose files trigger a
reboot loop reported on this model.

### 6. Verify and power cycle

Read the 35 back and **compare byte for byte against the target**. State the
count. `Error: Cannot overwrite backup` is a known false positive: the check
compares the entire blob and things like battery level drift between write and
read-back. The reads are the truth, not the message.

Then: unplug USB, power off, **battery out ~10 s**. A normal power-off is not
enough.

## Beyond languages

The same backup holds four more properties. Values from `tweaks.py`:

| Feature | Address | Size | Stock | Unlocked |
|---|---|---|---|---|
| PAL/NTSC selector | `0x01070148` | 1 | `00` | `01` |
| Recording limit | `0x003c0373`+0..2 | 3×1 | `00 1d 32` | `0d 01 00` |
| 4K recording limit | `0x003c04b6` | 2 LE | `2c 01` | `ff 7f` |
| USB app installer | `0x01640001` | 1 | `00` | `01` |

**Lead with PAL/NTSC on an import.** A body sold in a 60Hz market is locked to
NTSC (60p/30p/24p); exposing the selector is how it gets 50Hz PAL — 25p and
50p — which is what avoids flicker under 50Hz mains lighting and what
European delivery specs expect. For a European user with a Japanese camera
this is often more useful day to day than the menu language.

Two caveats to state, not skip:

- The recording-limit tweaks target the 29:59 cap Sony dropped around 2019.
  Recent bodies already ship unlimited, so **read before writing** — the
  table's "stock" is not their stock, and writing it would *impose* a limit
  that was never there.
- The USB app installer only matters on PlayMemories-era bodies (2012–2017).
  On a ZV-E10 II, which has no PMCA subsystem, it does nothing.

Use `stock`/`unlock` as the vocabulary, never `on`/`off`: "recording limit on"
does not say whether the limit or the tweak is on.

These go through upstream `bk patch` — one blob rewrite per property, so keep
the set small. No extra patch needed.

## Errors and what they actually mean

| Message | Reality |
|---|---|
| `Senser adjust control error 129` | Protected property. Use the PDT path. Session stays alive. |
| `Cannot overwrite backup` | False positive. Verify by reading. |
| `No tweaks available` | `PDT_READ` failed; the exception is swallowed silently. Use `bk w`. Session is dead: battery out. |
| Bare `Error:` cascading | USB session dead. Battery out ~10 s. |
| `ModuleNotFoundError: axmlparserpy` | `sudo` dropped the venv. Absolute path to the interpreter. |
| `[Errno 13] Access denied` | Missing `sudo`, or something holds the USB interface. |

`bk unlock` does **not** fix the 129: it is `setBackupId1(0)`, a different
permission mechanism. Tested in both ID1 states, it fails the same.

## Scripting the shell

`pmca/shell/interactive.py` reads with `sys.stdin.readline()`, so it accepts
piped commands. But the main loop catches `KeyboardInterrupt` and **not**
`EOFError`: if stdin closes at the prompt, it skips `backend.stop()` and
leaves the camera in service mode. Always send `exit`.

The `tweak` menu can only be left with `0` (which **applies**), Ctrl-C or EOF
— never leave it half-done over a pipe.

## Reference

Full procedure, scripts and the `lang` command patch:
<https://github.com/jaluma/zv-e10ii-language-unlock>
