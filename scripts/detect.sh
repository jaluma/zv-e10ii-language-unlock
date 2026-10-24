#!/bin/zsh
# Waits for a Sony device to appear on USB and describes it.
# Useful when it is unclear whether the cable, the USB mode or the camera is
# the problem.
echo "Waiting for the camera... (plug it in and power it on; Ctrl-C to quit)"
echo
i=0
while (( i < 45 )); do
  IOR=$(ioreg -p IOUSB -l -w 0 2>/dev/null)
  if print -r -- "$IOR" | grep -q '"idVendor" = 1356'; then
    echo ">>> SONY DEVICE DETECTED"
    echo
    print -r -- "$IOR" | grep -E '"USB Product Name"|"USB Vendor Name"|"idVendor"|"idProduct"|"USB Serial Number"|"bInterfaceClass"|"bInterfaceSubClass"' | sed 's/^ *//' | sort -u
    echo
    echo "bInterfaceClass 8 = Mass Storage (what you need)"
    echo "bInterfaceClass 6 = MTP/PTP      (change the USB mode on the camera)"
    exit 0
  fi
  (( i % 5 == 0 )) && echo "[${i}] devices on the bus: $(print -r -- "$IOR" | grep -c idProduct)"
  (( i++ ))
  /bin/sleep 2
done
echo
echo ">>> TIMED OUT. Nothing with idVendor 0x054C showed up."
echo "Prime suspect: a charge-only USB-C cable. Try the one from the camera."
echo
echo "Bus inventory:"
ioreg -p IOUSB -l -w 0 2>/dev/null | grep -E '"USB Product Name"|"idVendor"' | sed 's/^ *//' || echo "  (empty)"
exit 1
