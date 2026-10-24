# Protocol findings

Reverse-engineering notes from a real session on a **ZV-E10 II (`ZV-E10M2`),
region `CX89300_J1`**, with Sony-PMCA-RE at `a82f5ba`.

## The language map

35 **one-byte** properties, consecutive, in the backup:

```
0x010d008f  ..  0x010d00b1      # BASE + i, i = 0..34
0x01 = language enabled
0x02 = language disabled
```

Defined in `pmca/platform/backup.py`:

```python
self.addProp('language', CompoundBackupProp(
    dataInterface, [(0x010d008f + i, 1) for i in range(35)]))
```

**Index 1 is Japanese.** It follows from being the only one set in the `J1`
row of `getDefaultLanguages`, and a real read confirmed it: the Japanese body
returned `01` at exactly that position and `02` on the other 34.

```
BEFORE : 01000000000000000000000000000000000      1/35
```

## The other tweakable properties

Also in `BackupInterface`, with the on/off values taken from `tweaks.py`:

| Property | Address | Size | Stock | Unlocked |
|---|---|---|---|---|
| `palNtscSelector` | `0x01070148` | 1 | `00` | `01` |
| `recLimit` | `0x003c0373` + 0..2 | 3 × 1 | `00 1d 32` (29m50s) | `0d 01 00` (13h01m) |
| `recLimit4k` | `0x003c04b6` | 2 (LE) | `2c 01` (300s) | `ff 7f` (0x7fff s) |
| `usbAppInstaller` | `0x01640001` | 1 | `00` | `01` |

`recLimit` is three separate single-byte properties — hours, minutes, seconds
— not one three-byte property, so it needs three writes. `recLimit4k` is a
single little-endian 16-bit value in seconds.

Read-only informational properties worth dumping: `modelCode` (`0x00e70000`,
5 bytes), `modelName` (`0x003e0005`, 16), `serialNumber` (`0x00e70003`, 4),
`androidPlatformVersion` (`0x01660024`, 8).

`palNtscSelector` is the one that matters most on an import. A body sold in a
60Hz market is locked to NTSC; exposing the selector is how it gets 50Hz PAL
frame rates. The recording-limit tweaks are historical: they target the 29:59
cap that Sony dropped around 2019, so on a recent body the stock bytes will
not match what the table expects. Read before writing.

## The three `AdjustControl` commands

```python
# pmca/usb/sony.py
SONY_ADJUST_BACKUP_READ      = (0x603, 1)
SONY_ADJUST_BACKUP_WRITE     = (0x603, 2)
SONY_ADJUST_BACKUP_SAVE      = (0x603, 3)
SONY_ADJUST_BACKUP_PDT_WRITE = (0x603, 4)
SONY_ADJUST_BACKUP_PDT_READ  = (0x603, 5)
SONY_ADJUST_BACKUP_ID1       = (0x603, 15)
```

Measured on this body:

| Command | Shell | Result |
|---|---|---|
| `BACKUP_READ` | `bk r <ID>` | works |
| `BACKUP_WRITE` | `bk w <ID> <DATA>` | **`Senser adjust control error 129`** |
| `BACKUP_ID1` | `bk lock` / `bk unlock` | does not raise, but changes nothing |
| `PDT_READ` + `PDT_WRITE` | `bk patch`, `tweak`, `lang` | **works** |

The error comes from `_sendAdjustControlPacket`, which requires `res == 0`:

```python
def _sendAdjustControlPacket(self, block, code, data=b''):
    header = self.CommandHeader.pack(category=block, command=code)
    res, data = self.dev.sendSenserPacket(self.SONY_PFUNC_AdjustControl, header + data)
    if res != 0:
        raise Exception('Senser adjust control error %d' % res)
```

`129` is `0x81`, returned by the firmware.

## Why 129

The language properties carry a protection bit in their attribute. The PDT
path clears it temporarily; the per-property path never looks at it:

```python
# BackupPatchDataInterface.apply()
patchAttr = {}
for id, data in self.patch.items():
    p = self.backup.getProperty(id)
    if p.data != data and p.attr & 1:                  # protected
        patchAttr[id] = p.attr
        self.backup.setPropertyAttr(id, p.attr & ~1)   # clear
    self.backup.setProperty(id, data)
try:
    super().apply()          # checksum + PDT_WRITE of the whole blob
finally:
    if patchAttr:            # and restore the attributes
        for id, attr in patchAttr.items():
            self.backup.setPropertyAttr(id, attr)
        super().apply()
```

`bk w` calls `writeBackup(id, data)` → `BACKUP_WRITE` directly. Without
clearing the bit, the firmware refuses the write.

## The ID1 red herring

`bk unlock` looks like what you need, but:

```python
def setBackupProtection(self, enable):   # backend/senser.py
    self.dev.setBackupId1(enable)
# bk unlock -> setBackupProtection(False) -> setBackupId1(0)
# bk lock   -> setBackupProtection(True)  -> setBackupId1(1)
```

In Sony's service protocol ID1 is usually a permission level where `1`
**grants** access, so the polarity looked inverted. Tested with a no-op write
(rewriting `01` where `01` already was) in both states:

```
> bk r 0x010d0090      -> 01
> bk lock
> bk w 0x010d0090 01   -> Error: Senser adjust control error 129
> bk r 0x010d0090      -> 01
> bk unlock
> bk w 0x010d0090 01   -> Error: Senser adjust control error 129
> bk r 0x010d0090      -> 01
```

Hypothesis dead. Neither ID1 call raises, yet the write fails the same: ID1 is
a coarser mechanism that does not cover the per-property bit. The shell also
discards `setBackupId1`'s response byte, so its silence proves nothing.

Full log: [`logs/probe-id1-20261024-221107.log`](../logs/probe-id1-20261024-221107.log)

## Compared with the A7 IV

[Issue #744] documents the opposite on an A7 IV at fw 6.01: `PDT_READ` fails,
`tweak` reports `No tweaks available` (because `TweakInterface.__init__`
swallows the exception and leaves the list empty), the USB session is left
unusable and needs a battery pull — while `bk w` works perfectly.

Conclusion: **neither path is universal.** You have to probe. On the ZV-E10 II
the `bk w` failures do **not** kill the session; you can keep reading and
writing over PDT on the same connection.

## The verification false positive

```python
# BackupPlatformFileDataInterface.apply()
def apply(self):
    self.updateChecksum()
    data = self.file.getvalue()
    self.backend.setBackupData(data)
    if self.backend.getBackupData()[0x100:self.getSize()] != data[0x100:self.getSize()]:
        raise Exception('Cannot overwrite backup')
```

It compares the **entire** blob from `0x100`, not just the bytes touched.
Things that change on their own (battery level, use counters) break the
comparison even when the write was correct.

On the real run the error appeared **and the result was exact**:

```
> lang 01 01 01 ... 02
Error: Cannot overwrite backup
# 35 verification reads:
11111110000110011111110001010010000      19/35   <- the target, exactly
```

The reads are the source of truth. Same behaviour reported in [#550] on a
ZV-E10 II under Linux.

## Recommended probe

`bk patch <ID> <CURRENT_VALUE>` exercises `PDT_READ → setProperty → checksum →
PDT_WRITE → verification` while writing byte-identical content. It is the
minimum operation that answers whether the path works:

```
> bk r 0x010d0090        -> 01
> bk patch 0x010d0090 01 -> Success
> bk r 0x010d0090        -> 01
```

If the `bk patch` fails in the constructor, `PDT_READ` is broken on that body
and `bk w` is the path to use.

## macOS specifics

- **`system_profiler SPUSBDataType` can return zero devices** with the camera
  connected and working. `ioreg -p IOUSB -l -w 0` does list it. This is behind
  a lot of false "it does not detect the camera" reports.
- `serviceshell` takes no `-d` flag; it picks the driver itself and on macOS
  uses libusb with no intervention. No Zadig and no driver swapping, unlike
  Windows.
- `sudo` is mandatory: without it `detach_kernel_driver` fails with
  `[Errno 13] Access denied`.
- `sudo` **drops out of the venv** into the system Python. Invoke the
  interpreter by absolute path, or you get
  `ModuleNotFoundError: No module named 'axmlparserpy'`.
- A `sudo -v` from another terminal does not help: macOS caches the credential
  per tty.
- Python **3.11**, not the newest: `requirements.txt` pins `pycparser==2.17`
  and `axmlparserpy==0.0.4`.

## Scripting the shell

`pmca/shell/interactive.py` reads with `sys.stdin.readline()` in a loop, so
the shell accepts piped commands. Three things to know:

- The `>` prompt is printed **without a newline**, so in the output it ends up
  glued to the value: `>01`, not `01`. Strip it when parsing.
- The main loop catches `KeyboardInterrupt` but **not** `EOFError`. If stdin
  closes at the top-level prompt, the exception escapes `run()` and skips
  `backend.stop()`, leaving the camera in service mode. Always send `exit`.
- The interactive `tweak` menu can only be left with `0` (which **applies**),
  Ctrl-C, or EOF. It cannot be abandoned cleanly over a pipe, which is why
  `lang` exists as a non-interactive command.

[Issue #744]: https://github.com/ma1co/Sony-PMCA-RE/issues/744
[#550]: https://github.com/ma1co/Sony-PMCA-RE/issues/550
