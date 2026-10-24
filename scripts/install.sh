#!/bin/zsh
# Sets up a patched Sony-PMCA-RE in $PMCA_DIR (default ~/Sony-PMCA-RE).
set -eu
PMCA_DIR="${PMCA_DIR:-$HOME/Sony-PMCA-RE}"
HERE="${0:A:h}"
REPO="$HERE/.."

if [[ -e "$PMCA_DIR" ]]; then
  echo "ERROR: $PMCA_DIR already exists. Remove it, or export another PMCA_DIR."
  exit 1
fi

command -v brew >/dev/null || { echo "ERROR: Homebrew required."; exit 1; }

# Python 3.11 on purpose: PMCA-RE's requirements.txt pins pycparser==2.17 and
# axmlparserpy==0.0.4, which do not build on newer Python.
echo "== dependencies =="
brew list python@3.11 >/dev/null 2>&1 || brew install python@3.11
brew list libusb      >/dev/null 2>&1 || brew install libusb
command -v git >/dev/null || brew install git

echo "== cloning Sony-PMCA-RE =="
git clone https://github.com/ma1co/Sony-PMCA-RE.git "$PMCA_DIR"

echo "== applying the 'lang' command =="
cd "$PMCA_DIR"
git apply --check "$REPO/patches/0001-add-lang-command.patch"
git apply "$REPO/patches/0001-add-lang-command.patch"

echo "== virtualenv =="
"$(brew --prefix python@3.11)/bin/python3.11" -m venv .venv
./.venv/bin/python -m pip install --quiet --upgrade pip
./.venv/bin/python -m pip install --quiet -r requirements.txt

echo "== verification =="
./.venv/bin/python pmca-console.py --help >/dev/null && echo "  pmca-console: OK"
./.venv/bin/python -c "
import usb.backend.libusb1 as l
assert l.get_backend() is not None, 'pyusb cannot find libusb'
print('  libusb: OK')"
./.venv/bin/python -c "
import sys; sys.path.insert(0,'.')
from pmca.platform import CameraShell
assert hasattr(CameraShell, 'setLanguages'), 'patch did not apply'
print('  lang command: OK')"

echo
echo "Done. Next:"
echo "  $(cd "$REPO" && pwd)/scripts/run.sh recon"
