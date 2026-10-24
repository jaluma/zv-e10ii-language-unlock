#!/bin/zsh
# Driver for the Sony-PMCA-RE service shell.
#
#   ./run.sh recon                      read-only; ALWAYS start here
#   ./run.sh probe-features             read-only; what else is tweakable
#   ./run.sh probe-id1                  no-op; tests the per-property path
#   ./run.sh probe-pdt                  tests the PDT path (writes identical)
#   ./run.sh lang-cec                   Europe + Japanese = 19/35
#   ./run.sh lang-region CEC            any region in the table
#   ./run.sh lang-all                   all 35 languages
#   ./run.sh restore logs/recon-X.log   revert
#
#   ./run.sh pal-ntsc      unlock|stock   PAL/NTSC selector
#   ./run.sh rec-limit     unlock|stock   video recording time limit
#   ./run.sh rec-limit-4k  unlock|stock   4K recording time limit
#   ./run.sh usb-installer unlock|stock   USB app installer
#
# PMCA_DIR points at the patched Sony-PMCA-RE clone (see scripts/install.sh).
set -u
PMCA_DIR="${PMCA_DIR:-$HOME/Sony-PMCA-RE}"
HERE="${0:A:h}"
MODE="${1:-recon}"
ARG="${2:-}"

if [[ ! -x "$PMCA_DIR/.venv/bin/python" ]]; then
  echo "ERROR: no venv at $PMCA_DIR/.venv"
  echo "       run scripts/install.sh, or export PMCA_DIR"
  exit 1
fi

# --- Camera detection -------------------------------------------------------
# Note: `system_profiler SPUSBDataType` can come back empty on recent macOS
# even with the camera plugged in and working. ioreg is the reliable path.
DEV=$(ioreg -p IOUSB -l -w 0 2>/dev/null \
      | grep -E '"USB Product Name"|"idVendor"' \
      | grep -B1 '"idVendor" = 1356' \
      | grep '"USB Product Name"' | sed 's/.*= "//;s/"//' | head -1)
if [[ -z "$DEV" ]]; then
  echo "ERROR: no Sony device (idVendor 0x054C) on the USB bus."
  echo "       Put the camera in mass storage mode:"
  echo "         MENU > Setup > USB > USB Connection Mode > Mass Storage"
  echo "         (Japanese: セットアップ > USB > USB接続モード > マスストレージ)"
  echo "       Connect it over USB-C, leave it powered on, and quit Photos,"
  echo "       Image Capture, Dropbox and Google Drive."
  echo "       Run scripts/detect.sh to watch the bus while you plug it in."
  exit 1
fi
echo "== detected: $DEV =="

mkdir -p "$HERE/../logs"
LOG="$HERE/../logs/${MODE}-$(date +%Y%m%d-%H%M%S).log"

# Ask for the password now, on a real tty: sudo inside a pipeline cannot
# always open its prompt properly.
sudo -v || exit 1

echo "== mode: $MODE   log: $LOG =="
"$PMCA_DIR/.venv/bin/python" "$HERE/feed.py" "$MODE" ${ARG:+"$ARG"} \
  | ( cd "$PMCA_DIR" && sudo ./.venv/bin/python pmca-console.py serviceshell 2>&1 ) \
  | tee "$LOG"

# The '>' prompt is glued to the value in the output, hence the sed.
BYTES=$(sed 's/^>*//' "$LOG" | grep -E '^[0-9a-f]{2}$')
echo
echo "== property bytes read in this log =="
print -r -- "$BYTES" | tr '\n' ' '; echo
echo "== 01: $(print -r -- "$BYTES" | grep -cE '^01$')   02: $(print -r -- "$BYTES" | grep -cE '^02$') =="
echo "== log: $LOG =="
echo
echo "NOTE: 'Error: Cannot overwrite backup' is a known false positive."
echo "      The verification reads are the source of truth, not that message."
