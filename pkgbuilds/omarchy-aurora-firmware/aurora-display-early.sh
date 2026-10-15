#!/bin/bash
# SPDX-License-Identifier: MIT
# Load the Apple display driver on the MacBook Neo before udev coldplug reaches
# it. The USB-C external display (DCPEXT) needs appledrm twice over: it drives
# the display, and it provides the Type-C display route that the sn201202x port
# waits for before it sets the DisplayPort mux. With the lid closed, the
# passphrase prompt and the boot console then appear on the external display
# about as soon as the kernel can show them.
#
# Other machines are left to udev. A failed load never blocks the boot: udev
# loads the same module again when it reaches the device.
set -u
compatible=${AURORA_DT_COMPATIBLE:-/sys/firmware/devicetree/base/compatible}
modprobe_command=${AURORA_MODPROBE:-modprobe}

grep -aq 'apple,j700' "$compatible" 2>/dev/null || exit 0
"$modprobe_command" -q appledrm ||
  echo 'Aurora: early appledrm load failed; udev will load it' >&2
exit 0
