# Troubleshooting

| Symptom | Actual cause | What to do |
|---|---|---|
| `Senser adjust control error 129` on every `bk w` | The language properties carry the protection bit (`attr & 1`) and `BACKUP_WRITE` refuses protected properties. `bk unlock` does not fix it. | Use the PDT path: `lang`, `bk patch` or `tweak`. The session **stays alive** after these errors; no battery pull needed. |
| `Error: Cannot overwrite backup` | False positive. The verification compares the whole blob from `0x100`, not just the bytes touched. | Ignore it and read the properties back. Those reads are the truth. |
| `No tweaks available` | `PDT_READ` fails and `TweakInterface.__init__` swallows the exception, leaving the tweak list empty. Not a driver problem. | On that body the PDT path is closed; try `bk w`. Recover the session first: the failed read leaves it unusable. |
| Bare `Error:` on everything, even reads | `GenericUsbException`. The USB session died after a failed backup read. | Power off, **pull the battery ~10 s**, reinsert, reconnect. A normal power-off does not recover it. |
| `system_profiler SPUSBDataType` returns nothing | On recent macOS it can list nothing with the camera connected. | Use `ioreg -p IOUSB -l -w 0 \| grep -E '"USB Product Name"\|"idVendor"'`. Look for `idVendor = 1356` (`0x054C`). Or run `scripts/detect.sh`. |
| `ModuleNotFoundError: axmlparserpy` | `sudo` drops out of the venv into the system Python. | Invoke the interpreter by absolute path: `sudo ./.venv/bin/python …` |
| `[Errno 13] Access denied` | Missing `sudo`, or another process holds the USB interface. | Use `sudo`. Quit Photos, Image Capture, Dropbox, Google Drive. If it persists, reboot. |
| `No devices found` | The driver flag is missing on the `info` subcommand. | `pmca-console.py info -d libusb`. `serviceshell` does not need it. |
| `USB resource busy` | A previous session is stuck. | Reboot the Mac. |
| HTTP errors | The tool needs network access on some steps. | Stay online. |
| `pmca-console info` hangs | Reported on some bodies for the top-level subcommand. | Use the `info` inside `serviceshell`. |
| Nothing at all on the USB bus | Most likely a **charge-only USB-C cable**. | Use the camera's own cable. Check it is powered on with charge. Try another port. `scripts/detect.sh` watches the bus while you plug it in. |
| `bInterfaceClass = 6` instead of `8` | The camera is in MTP/PTP, not mass storage. | Switch `USB Connection Mode` to `Mass Storage`. |
| Reboot loop scrolling the language menu | The Chinese language files. Happens with all 35 languages enabled. | Use `lang-cec`, which leaves them off. If you already have 35/35, write the CEC pattern with `lang-region CEC`. |
| Camera does not ask for a language on boot | The flash sync needs a full power cycle. | Power off and **pull the battery for 10 s**. The setting also lives in the setup menu, under the area/date block (`エリア/日付`). |
| `rec-limit` stock bytes are not `00 1d 32` | Your body already ships without the 29:59 cap — Sony dropped it around 2019. | Nothing to unlock. Keep what `probe-features` read and leave it alone. |
| PAL/NTSC selector not visible after unlocking | Needs a full power cycle, like the language change. | Power off, pull the battery ~10 s. |

## Recovering a dead session

A normal power-off is **not** enough:

1. Power the camera off.
2. Remove the battery and wait ~10 seconds.
3. Reinsert, reconnect, run the script again.

## Reverting

```bash
./scripts/run.sh restore logs/recon-YYYYMMDD-HHMMSS.log
```

Uses the PDT path. As long as service mode stays reachable and you kept the
`recon` log, none of this is irreversible.

For the feature tweaks, `stock` writes the factory values back:

```bash
./scripts/run.sh pal-ntsc stock
```

But trust your own `probe-features` reading over the table: on a body that
never had the 29:59 cap, "stock" per the table is not your stock.

## If your body is not a ZV-E10 II

Run `recon`, `probe-features` and `probe-pdt` and look at what comes back.
Together they tell you whether the addresses line up and which write path is
open. If you want it documented, open an issue with those logs — the scripts
no longer print the serial number, but check before pasting.
