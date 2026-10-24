# Sony ZV-E10 II — language and feature unlock (Japanese body)

Enable English, Spanish and the rest of the menu languages on a **Sony
ZV-E10 II (`ZV-E10M2`) sold on the Japanese domestic market**, by writing the
camera's backup properties over the service-mode USB channel.

The Japanese body ships with **1 of 35 languages** and no language item in the
menu at all: it is not that Spanish is missing, there is no English either.

**Verified:** 1/35 → 19/35 on a ZV-E10 II, region `CX89300_J1`, from an Apple
Silicon MacBook, 24 October 2026. Full logs of every step in [`logs/`](logs/).

---

## The main finding

**The route every tutorial describes does not work on this camera.**

Sony's service protocol offers two ways to write the backup, and which one
works depends on the body:

| Protocol command | Shell command | A7 IV ([#744]) | ZV-E10 II |
|---|---|---|---|
| `BACKUP_READ` `(0x603, 1)` | `bk r` | works | works |
| `BACKUP_WRITE` `(0x603, 2)` | `bk w` | works | **`error 129`** |
| `BACKUP_PDT_READ/WRITE` `(0x603, 5/4)` | `tweak`, `bk patch` | fails, kills the session | **works** |

On the ZV-E10 II they are **inverted** relative to the only case that had been
documented. The cause of `error 129` is in PMCA-RE's own code: the language
properties carry a protection bit, and only the PDT path clears it before
writing.

```python
# pmca/platform/backup.py :: BackupPatchDataInterface.apply()
if p.data != data and p.attr & 1:                  # protection bit set
    self.backup.setPropertyAttr(id, p.attr & ~1)   # clear it
self.backup.setProperty(id, data)
```

`bk w` sends `BACKUP_WRITE` raw, the firmware sees a protected property and
answers 129. `bk unlock` is **not** the antidote: it is `setBackupId1(0)` and
`bk lock` is `setBackupId1(1)`, a polarity suspicious enough to be worth
testing — it fails with 129 in both ID1 states. It is a coarser permission
mechanism that does not cover the per-property bit.

Full write-up in [`docs/protocol-findings.md`](docs/protocol-findings.md).

## What this repo adds

`tweak` uses the PDT path but forces **all 35 languages**, and the Chinese
language files trigger a reboot loop reported on the ZV-E10 II ([#550]).
`bk patch` writes an arbitrary pattern, but each call rewrites the entire
blob: 35 calls would be 35 full rewrites.

Writing an arbitrary pattern in **one** operation needs a command that does
not exist upstream. Twelve lines reusing `BackupPatchDataInterface`, with its
protection-bit handling included:
[`patches/0001-add-lang-command.patch`](patches/0001-add-lang-command.patch)
(verified against `a82f5ba`).

```
> lang 01 01 01 01 01 01 01 02 02 02 02 01 01 02 02 01 01 01 01 01 01 01 02 02 02 01 02 01 02 02 01 02 02 02 02
Success: 19/35 languages enabled
```

The patterns are not invented: `scripts/feed.py` embeds PMCA-RE's
`getDefaultLanguages` table verbatim, so `lang-region CEC` writes exactly the
language set Sony ships on a Spanish-market ZV-E10 II.

## Beyond languages

The same backup holds four more tweakable properties. On an import, the first
one matters more day to day than the menu language:

| Feature | Property | Stock | Unlocked |
|---|---|---|---|
| **PAL / NTSC selector** | `0x01070148` | `00` hidden | `01` visible |
| Video recording limit | `0x003c0373`..`75` | `00 1d 32` → 29m50s | `0d 01 00` → 13h01m |
| 4K recording limit | `0x003c04b6` (LE16) | `2c 01` → 5m00s | `ff 7f` → 9h06m07s |
| USB app installer | `0x01640001` | `00` | `01` |

**The PAL/NTSC selector is the real prize on a Japanese body.** A JP camera is
locked to NTSC (60Hz), so you get 60p/30p/24p. Exposing the selector gives you
50Hz PAL — **25p and 50p** — which is what you need to avoid flicker under
50Hz mains lighting, and what European delivery specs expect.

```bash
./scripts/run.sh probe-features        # read-only: see what your body has
./scripts/run.sh pal-ntsc unlock       # expose the selector
```

These take `stock` or `unlock`, never `on`/`off` — "recording limit on" does
not say whether the limit or the tweak is on, and guessing wrong writes the
opposite of what you meant.

Two honest caveats. The recording-limit tweaks date from the era of the 29:59
cap, which Sony dropped industry-wide around 2019; bodies since then already
ship unlimited, so **run `probe-features` first** and keep whatever you read.
And the USB app installer is only meaningful on PlayMemories-era bodies
(2012–2017) — on a ZV-E10 II, which has no PMCA subsystem, it does nothing.

The feature writes go through upstream `bk patch`, one full blob rewrite per
property, so keep the set small. No extra patch needed.

## Usage

```bash
git clone https://github.com/jaluma/zv-e10ii-language-unlock.git
cd zv-e10ii-language-unlock
./scripts/install.sh          # clones PMCA-RE, applies the patch, builds the venv
```

Put the camera in mass storage mode and connect it over USB-C:

```
MENU > Setup > USB > USB Connection Mode > Mass Storage
Japanese: セットアップ > USB > USB接続モード > マスストレージ
```

Quit Photos, Image Capture, Dropbox and Google Drive — anything holding the
USB interface makes the connection fail with a misleading permissions error.
Then:

```bash
./scripts/run.sh recon        # READ-ONLY. Save the log: it is your rollback.
./scripts/run.sh probe-pdt    # confirm the PDT path works on your body
./scripts/run.sh lang-cec     # write Europe + Japanese = 19/35
```

Finally: unplug USB, power off, and **pull the battery for ~10 seconds**. A
normal power-off is not enough. On the next boot it asks for the language.

### Modes

| Mode | Writes | What it does |
|---|---|---|
| `recon` | no | `info` + the 35 language reads. **Always start here.** |
| `probe-features` | no | Reads every known tweakable property |
| `probe-id1` | no-op | Tests whether ID1 gates the per-property path |
| `probe-pdt` | identical | Exercises the whole PDT path without changing values |
| `lang-cec` | yes | Europe + Japanese = 19/35 (English and Spanish, no Chinese) |
| `lang-region REGION` | yes | Any region in the table (`U2`, `CEC`, `AP2`…) |
| `lang-all` | yes | All 35 languages |
| `restore FILE` | yes | Reverts to the state in a `recon` log |
| `pal-ntsc stock\|unlock` | yes | PAL/NTSC selector |
| `rec-limit stock\|unlock` | yes | Video recording time limit |
| `rec-limit-4k stock\|unlock` | yes | 4K recording time limit |
| `usb-installer stock\|unlock` | yes | USB app installer |

## Two things that look like failures and are not

**`Error: Cannot overwrite backup`** appeared on the real run **and the write
had succeeded perfectly**. The check in
`BackupPlatformFileDataInterface.apply()` compares the whole blob from `0x100`
after writing, and something unrelated to languages (battery level, use
counters) drifts between the write and the read-back. The verification reads
are the source of truth, not the tool's message.

**`system_profiler SPUSBDataType` returns nothing** on recent macOS even with
the camera plugged in and working. `ioreg` sees it, and that is what the
scripts use:

```bash
ioreg -p IOUSB -l -w 0 | grep -E '"USB Product Name"|"idVendor"'
# "USB Product Name" = "ZV-E10M2"
# "idVendor" = 1356            (0x054C, Sony)
# "bInterfaceClass" = 8        (Mass Storage, correct)
```

More cases in [`docs/troubleshooting.md`](docs/troubleshooting.md).

## Risks

- **You give up any official Sony service option.** You are writing into the
  region and calibration data area. A Japanese warranty is domestic-only
  anyway, so in practice there was no coverage to lose.
- **`recon` is not optional.** It is the only record that makes a rollback
  possible.
- **All 35 languages can trigger a reboot loop** from the Chinese language
  files ([#550]). `lang-cec` leaves them off on purpose.
- No bricked cameras have been reported from this procedure, but PMCA-RE's own
  README puts it plainly: *"If you break your camera, you get to keep both
  pieces."* This is not official Sony software.

## Rollback

```bash
./scripts/run.sh restore logs/recon-YYYYMMDD-HHMMSS.log
```

Goes through the same PDT path it was written with. On this body `bk w` does
not work for reverting either.

## Scope

Verified **only** on a ZV-E10 II `CX89300_J1` on Apple Silicon macOS. The
mechanism — per-property protection bit, PDT path — should apply to other
recent Sony bodies, but that is untested. If you try another model, the
`recon` and `probe-pdt` logs are what settles it. Open an issue.

## Credits

All the hard reverse-engineering work is
[**ma1co/Sony-PMCA-RE**](https://github.com/ma1co/Sony-PMCA-RE) and its
contributors. This repo adds one command and documents which protocol path
works on one specific body.

Reference threads: [#546] (ZV-E10 II on Windows), [#550] (Chinese reboot
loop), [#744] (`bk` path analysis), [#748] (macOS Apple Silicon).

[#546]: https://github.com/ma1co/Sony-PMCA-RE/issues/546
[#550]: https://github.com/ma1co/Sony-PMCA-RE/issues/550
[#744]: https://github.com/ma1co/Sony-PMCA-RE/issues/744
[#748]: https://github.com/ma1co/Sony-PMCA-RE/issues/748

## License

MIT. See [LICENSE](LICENSE).
