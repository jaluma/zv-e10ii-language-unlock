#!/usr/bin/env python3
"""Command generator for the Sony-PMCA-RE service shell.

Writes commands to stdout, paced, so they can be piped into
`pmca-console.py serviceshell`, whose main loop reads sys.stdin.readline().

    ./feed.py <mode> [arg] | sudo .venv/bin/python pmca-console.py serviceshell

Read-only modes (no risk):
    recon               info + the 35 language reads. Save the output: it is
                        your only rollback record.
    probe-features      Reads every known tweakable property. Tells you which
                        ones exist on your body before you try to write them.
    probe-id1           Checks whether `bk unlock`/`bk lock` enables the
                        per-property write path. True no-op: rewrites the
                        value that is already there.

Writing modes:
    probe-pdt           Exercises the whole PDT path writing byte-identical
                        content. The minimum operation that answers whether
                        the path works before you trust it.
    lang-region REGION  Writes that region's factory language set (see
                        REGIONS). One single PDT operation.
    lang-cec            Shorthand for CEC plus Japanese = 19/35.
    lang-all            All 35 languages.
    restore FILE        Reverts to the state in an earlier `recon` log.

Feature modes, each taking `stock` or `unlock`:
    pal-ntsc            PAL/NTSC selector. `unlock` exposes the menu item,
                        which is how a 60Hz-locked body gets 25p/50p.
    rec-limit           Video recording time limit: 29m50s -> 13h01m.
    rec-limit-4k        4K recording time limit: 5m00s -> 9h06m07s.
    usb-installer       USB app installer (PlayMemories-era bodies only).

Never `on`/`off` for these: "recording limit on" does not say whether the
limit or the tweak is on, and guessing wrong writes the opposite.

The protocol's two write paths are not equivalent and which one works depends
on the body. See docs/protocol-findings.md.
"""
import os
import sys
import time

LANG_BASE = 0x010D008F
LANG_N = 35
ENABLED, DISABLED = 0x01, 0x02

# Copied verbatim from pmca/platform/backup.py :: getDefaultLanguages
# (Sony-PMCA-RE @ a82f5ba). These are the factory language sets per region.
REGIONS = {
    'ALLLANG': [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],
    'AP2': [1,0,1,0,1,0,1,1,1,1,1,0,0,1,1,0,0,0,0,0,1,0,0,1,1,0,0,0,0,0,0,0,0,0,0],
    'AU2': [1,0,1,0,1,0,1,1,1,1,1,0,0,1,1,0,0,0,0,0,1,0,0,1,1,0,0,0,0,1,0,1,0,0,0],
    'CA2': [1,0,1,0,1,1,0,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
    'CE':  [1,0,1,1,1,1,1,0,0,0,0,1,1,0,0,1,1,1,1,1,1,1,0,0,0,1,0,1,0,0,0,0,0,0,0],
    'CE3': [1,0,1,1,1,1,1,0,0,0,0,1,0,0,0,1,1,1,1,1,1,1,1,0,0,1,1,1,1,0,0,0,0,0,0],
    'CE7': [1,0,1,0,1,0,1,1,1,1,1,0,0,1,1,0,0,0,0,0,1,0,0,1,1,0,0,0,0,1,0,1,0,0,0],
    'CEC': [1,0,1,1,1,1,1,0,0,0,0,1,1,0,0,1,1,1,1,1,1,1,0,0,0,1,0,1,0,0,1,0,0,0,0],
    'CEH': [1,0,1,1,1,1,1,0,0,0,0,1,0,0,0,1,1,1,1,1,1,1,1,0,0,1,1,1,1,0,0,0,0,0,0],
    'CN1': [1,0,1,0,1,0,1,1,1,1,1,0,0,1,1,0,0,0,0,0,1,0,0,1,1,0,0,0,0,1,0,1,0,0,0],
    'CN2': [1,0,1,0,1,0,1,1,1,1,1,0,0,1,1,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,1,0,0,0],
    'E32': [1,0,1,0,1,0,1,1,1,1,1,0,0,1,1,0,0,0,0,0,1,0,0,1,1,0,0,0,0,1,0,1,0,0,0],
    'E33': [1,0,1,0,1,0,1,1,1,1,1,0,0,1,1,0,0,0,0,0,1,0,0,1,1,0,0,0,0,1,0,1,0,0,0],
    'E37': [1,0,1,0,1,0,1,1,1,1,1,0,0,1,1,0,0,0,0,0,1,0,0,1,1,0,0,0,0,1,0,1,0,0,0],
    'E38': [1,0,1,0,1,0,1,1,1,1,1,0,0,1,1,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,1,0,0,0],
    'EA8': [1,0,1,0,1,0,1,1,1,1,1,0,0,1,1,0,0,0,0,0,1,0,0,1,1,0,0,0,0,1,0,1,0,0,0],
    'HK1': [1,0,1,0,1,0,1,1,1,1,1,0,0,1,1,0,0,0,0,0,1,0,0,1,1,0,0,0,0,1,0,1,0,0,0],
    'IN5': [1,0,1,0,1,0,1,1,1,1,1,0,0,1,1,0,0,0,0,0,1,0,0,1,1,0,0,0,0,0,0,0,0,0,0],
    'J1':  [0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
    'JE3': [1,0,1,0,1,0,1,1,1,1,1,0,0,1,1,0,0,0,0,0,1,0,0,1,1,0,0,0,0,0,0,0,0,0,0],
    'KR2': [1,0,1,0,1,0,1,1,1,1,1,0,0,1,1,0,0,0,0,0,1,0,0,1,1,0,0,0,0,1,0,1,0,0,0],
    'RU2': [1,0,1,1,1,1,1,0,0,0,0,1,1,0,0,1,1,1,1,1,1,1,0,0,0,1,0,1,0,0,0,0,0,0,0],
    'RU3': [1,0,1,1,1,1,1,0,0,0,0,1,1,0,0,1,1,1,1,1,1,1,1,0,0,1,1,1,0,0,1,0,0,0,0],
    'TW6': [1,0,1,0,1,0,1,1,1,1,1,0,0,1,1,0,0,0,0,0,1,0,0,1,1,0,0,0,0,1,0,1,0,0,0],
    'U2':  [1,0,1,0,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
    'UC2': [1,0,1,0,1,1,0,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
}

# Index 1 is Japanese: it is the only one set in the J1 row, and a real read of
# a CX89300_J1 body confirmed it (1/35, the 01 sitting at position 1).
IDX_JAPANESE = 1

# Other tweakable properties, from pmca/platform/backup.py and tweaks.py.
# Each entry: list of (address, [stock bytes], [unlocked bytes]).
#
# Every feature takes `stock` or `unlock`, never `on`/`off`: "recording limit
# on" is ambiguous about whether the limit or the tweak is on, and getting it
# backwards writes the opposite of what you meant.
#
# PAL/NTSC is the interesting one on an import. A Japanese body is locked to
# NTSC (60Hz): 60p/30p/24p. Exposing the selector is how you get 50Hz PAL,
# i.e. 25p/50p, which is what avoids flicker under 50Hz mains lighting.
FEATURES = {
    'pal-ntsc': {
        'desc': 'PAL / NTSC selector',
        'props': [(0x01070148, [0x00], [0x01])],
        'stock_str': 'hidden (body locked to its region system)',
        'unlock_str': 'selector visible in the menu',
        'note': 'Needs a power cycle. On a 60Hz body this is what unlocks '
                '25p/50p.',
    },
    'rec-limit': {
        'desc': 'Video recording time limit',
        # 3 consecutive 1-byte properties: hours, minutes, seconds.
        'props': [(0x003C0373, [0x00], [0x0D]),      # h: 0  -> 13
                  (0x003C0374, [0x1D], [0x01]),      # m: 29 -> 1
                  (0x003C0375, [0x32], [0x00])],     # s: 50 -> 0
        'stock_str': '29m50s',
        'unlock_str': '13h01m',
        'note': 'Bodies from ~2019 on already ship unlimited, in which case '
                'the stock bytes will not be 00 1d 32. Run probe-features '
                'first and keep what you read.',
    },
    'rec-limit-4k': {
        'desc': '4K recording time limit',
        # Single 2-byte little-endian property: seconds.
        'props': [(0x003C04B6, [0x2C, 0x01], [0xFF, 0x7F])],   # 300s -> 0x7fff
        'stock_str': '5m00s (300s)',
        'unlock_str': '9h06m07s (0x7fff s)',
        'note': 'Same caveat as rec-limit: check what is actually there first.',
    },
    'usb-installer': {
        'desc': 'USB app installer',
        'props': [(0x01640001, [0x00], [0x01])],
        'stock_str': 'disabled',
        'unlock_str': 'enabled',
        'note': 'Only meaningful on PlayMemories-era bodies (2012-2017). '
                'Useless on a ZV-E10 II, which has no PMCA subsystem.',
    },
}

# Read-only informational properties.
INFO_PROPS = [
    (0x00E70000, 5,  'modelCode'),
    (0x003E0005, 16, 'modelName'),
    (0x01660024, 8,  'androidPlatformVersion'),
]


def emit(lines, pace=0.35):
    try:
        for ln in lines:
            sys.stdout.write(ln + "\n")
            sys.stdout.flush()
            time.sleep(pace)
    except BrokenPipeError:
        # The service shell already closed after 'exit'. Normal, not a failure.
        try:
            sys.stdout.close()
        except Exception:
            pass
        os._exit(0)


def lang_reads():
    return ["bk r 0x%08x" % (LANG_BASE + i) for i in range(LANG_N)]


def feature_reads():
    """One read per byte of every feature property, plus the info ones."""
    out = []
    for key in sorted(FEATURES):
        for addr, stock, _ in FEATURES[key]['props']:
            for off in range(len(stock)):
                out.append("bk r 0x%08x" % (addr + off))
    for addr, size, _ in INFO_PROPS:
        out.append("bk r 0x%08x" % addr)
    return out


def lang_cmd(pattern):
    """One single PDT operation. Needs patches/0001-add-lang-command.patch."""
    if len(pattern) != LANG_N:
        sys.exit("pattern must hold %d values, got %d" % (LANG_N, len(pattern)))
    return "lang " + " ".join("%02x" % (ENABLED if v else DISABLED) for v in pattern)


def feature_cmds(key, unlock):
    """Per-property PDT writes via upstream `bk patch`.

    `bk w` is deliberately avoided: on some bodies, this one included, it
    returns `Senser adjust control error 129` because it never clears the
    per-property protection bit. `bk patch` goes through the PDT path, which
    does. One full blob rewrite per property, so keep the set small.
    """
    f = FEATURES[key]
    out = []
    for addr, stock, unlocked in f['props']:
        value = unlocked if unlock else stock
        out.append("bk patch 0x%08x %s" % (addr, " ".join("%02x" % b for b in value)))
    return out


def parse_recon(path):
    """Pull the 35 language bytes out of a recon log.

    The '>' prompt is printed without a newline, so it ends up glued to the
    value: '>01', not '01'.
    """
    vals = []
    with open(path, "r", errors="replace") as f:
        for line in f:
            s = line.strip().lstrip(">").strip()
            if s in ("01", "02", "0x01", "0x02"):
                vals.append(1 if s.endswith("1") else 0)
    if len(vals) < LANG_N:
        sys.exit("%s: expected at least %d values, found %d" % (path, LANG_N, len(vals)))
    # A write log holds reads before and after; the first 35 are the original
    # state, which is what we want to restore.
    return vals[:LANG_N]


def lang_session(pattern):
    """Backup reads, the write, then verification reads."""
    return ["info"] + lang_reads() + [lang_cmd(pattern)] + lang_reads() + ["exit", ""]


def feature_session(key, unlock):
    reads = ["bk r 0x%08x" % (a + o)
             for a, stock, _ in FEATURES[key]['props']
             for o in range(len(stock))]
    return ["info"] + reads + feature_cmds(key, unlock) + reads + ["exit", ""]


def want_unlock(argv, mode):
    f = FEATURES[mode]
    if len(argv) < 2 or argv[1] not in ("stock", "unlock"):
        sys.exit("usage: feed.py %s stock|unlock\n"
                 "  %s\n"
                 "  stock  -> %s\n"
                 "  unlock -> %s\n"
                 "  %s" % (mode, f['desc'], f['stock_str'], f['unlock_str'], f['note']))
    return argv[1] == "unlock"


def main():
    argv = sys.argv[1:]
    mode = argv[0] if argv else "recon"

    if mode == "recon":
        emit(["info"] + lang_reads() + ["exit", ""])

    elif mode == "probe-features":
        emit(["info"] + feature_reads() + ["exit", ""], pace=0.3)

    elif mode == "probe-id1":
        # No-op: rewrites the value Japanese already has. Pass or fail, the
        # state does not change. Answers whether ID1 gates the per-property
        # write path.
        addr = "0x%08x" % (LANG_BASE + IDX_JAPANESE)
        emit(["info",
              "bk r " + addr,
              "bk lock",   "bk w " + addr + " 01", "bk r " + addr,
              "bk unlock", "bk w " + addr + " 01", "bk r " + addr,
              "exit", ""], pace=0.5)

    elif mode == "probe-pdt":
        # Writes the full blob with identical content. Exercises
        # PDT_READ -> setProperty -> checksum -> PDT_WRITE -> verification.
        addr = "0x%08x" % (LANG_BASE + IDX_JAPANESE)
        emit(["info", "bk r " + addr, "bk patch " + addr + " 01", "bk r " + addr,
              "exit", ""], pace=0.8)

    elif mode == "lang-region":
        if len(argv) < 2 or argv[1] not in REGIONS:
            sys.exit("usage: feed.py lang-region REGION\nregions: %s"
                     % ", ".join(sorted(REGIONS)))
        emit(lang_session(REGIONS[argv[1]]))

    elif mode == "lang-cec":
        # CEC (Europe) plus Japanese. Includes English and Spanish; leaves
        # Chinese off, whose files trigger a reboot loop on the ZV-E10 II.
        pattern = list(REGIONS['CEC'])
        pattern[IDX_JAPANESE] = 1
        emit(lang_session(pattern))

    elif mode == "lang-all":
        emit(lang_session(REGIONS['ALLLANG']))

    elif mode == "restore":
        if len(argv) < 2:
            sys.exit("usage: feed.py restore logs/recon-XXX.log")
        emit(lang_session(parse_recon(argv[1])))

    elif mode in FEATURES:
        emit(feature_session(mode, want_unlock(argv, mode)), pace=0.5)

    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
